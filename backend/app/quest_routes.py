"""State-only API. Creation/replan remain internal until AI orchestration exists."""
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.routing import APIRoute
from pydantic import UUID4

from .errors import QuestError
from .schemas import CompletionView, ErrorView, ProfileView, QuestlineList, QuestlineView, RevisionRequest
from .services.quests import QuestService


class ProductRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def guarded(request: Request):
            request.state.product_request_id = str(uuid4())
            try:
                response = await handler(request)
            except QuestError:
                raise
            except Exception as exc:
                from fastapi.exceptions import RequestValidationError
                if isinstance(exc, RequestValidationError):
                    raise
                # Suppress exception text/SQL/inputs; application does not log private state.
                raise QuestError("INTERNAL_ERROR", 500, "The operation failed. Reload and try again.", True) from None
            response.headers["Cache-Control"] = "no-store"
            return response
        return guarded


def get_quests(request: Request) -> QuestService:
    if not getattr(request.app.state, "database_available", False):
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Local storage is unavailable. Check the database path and schema.", True)
    return request.app.state.quests


QuestDependency = Annotated[QuestService, Depends(get_quests)]
KeyHeader = Annotated[UUID4, Header(alias="Idempotency-Key")]
router = APIRouter(prefix="/api", route_class=ProductRoute,
                   responses={404: {"model": ErrorView}, 409: {"model": ErrorView},
                              422: {"model": ErrorView}, 503: {"model": ErrorView}, 500: {"model": ErrorView}})


@router.get("/profile", response_model=ProfileView)
def profile(quests: QuestDependency) -> ProfileView:
    return quests.get_profile()


@router.get("/questlines", response_model=QuestlineList)
def saved_questlines(quests: QuestDependency, limit: Annotated[int, Query(ge=1, le=100)] = 20,
                    offset: Annotated[int, Query(ge=0)] = 0,
                    status: Literal["active", "paused", "completed"] | None = None) -> QuestlineList:
    return quests.list_questlines(limit=limit, offset=offset, status=status)


@router.get("/questlines/{id}", response_model=QuestlineView)
def questline(id: UUID4, quests: QuestDependency) -> QuestlineView:
    return quests.get_questline(str(id))


@router.post("/quests/{id}/complete", response_model=CompletionView)
def complete(id: UUID4, body: RevisionRequest, quests: QuestDependency) -> CompletionView:
    return quests.complete_quest(str(id), body.expected_revision)


@router.post("/questlines/{id}/pause", response_model=QuestlineView)
def pause(id: UUID4, body: RevisionRequest, idempotency_key: KeyHeader, quests: QuestDependency) -> QuestlineView:
    return quests.set_paused(str(id), body.expected_revision, paused=True, idempotency_key=str(idempotency_key))


@router.post("/questlines/{id}/resume", response_model=QuestlineView)
def resume(id: UUID4, body: RevisionRequest, idempotency_key: KeyHeader, quests: QuestDependency) -> QuestlineView:
    return quests.set_paused(str(id), body.expected_revision, paused=False, idempotency_key=str(idempotency_key))
