"""Persistent context and local AI orchestration; no write unit spans inference."""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ..database import unit_of_work
from ..errors import QuestError
from ..models import CheckIn, GenerationIntent, Quest, Questline, TransitionReceipt
from ..ollama import CandidateAssessment, OllamaClient, QuestGenerationError, QuestPlanResult, require_local_url
from ..quality import QUALITY_VERSION, clarification_question, essential_checks, reject_semantics, validate_answer
from ..schemas import (
    CheckInAnswer, CheckInStart, CheckInView, CompletedMilestone, GenerateQuestlineRequest,
    GroundingContext, QuestlineContext, QuestlineView, ReplanRequest, SemanticReview,
)
from .quests import QuestService, check_revision, context_values, get_line, public_view, utc_text, valid_id

LEASE_SECONDS = 135
PIPELINE_SECONDS = 120


def request_hash(operation: str, target: str, body: dict) -> str:
    encoded = json.dumps({"operation": operation, "target": target, "body": body}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def get_check_in(session, check_in_id: str) -> CheckIn:
    result = session.get(CheckIn, check_in_id)
    if result is None:
        raise QuestError("CHECK_IN_NOT_FOUND", 404, "Check-in not found.")
    return result


def check_in_context(check_in: CheckIn) -> QuestlineContext:
    return QuestlineContext(goal=check_in.goal, available_minutes=check_in.available_minutes, energy=check_in.energy,
                            deadline=check_in.deadline, contextual_notes=check_in.contextual_notes)


def check_in_view(check_in: CheckIn) -> CheckInView:
    return CheckInView(id=check_in.id, status=check_in.status, revision=check_in.revision,
                       context=check_in_context(check_in), question=check_in.follow_up_question if check_in.status == "needs_follow_up" else None,
                       summary=check_in.summary, questline_id=check_in.questline_id, clarification_answer=check_in.follow_up_answer,
                       created_at=check_in.created_at, updated_at=check_in.updated_at)


def summary_for(goal: str, answer: str | None) -> str:
    # Deterministic convenience summary, never a replacement for the complete stored goal/answer.
    return (goal if answer is None else f"Goal: {goal[:900]}\nUser clarification: {answer[:1000]}")[:2000]


def conflict() -> QuestError:
    return QuestError("IDEMPOTENCY_CONFLICT", 409, "This idempotency key belongs to a different request.")


def in_progress(expires: str) -> QuestError:
    seconds = max(1, math.ceil((datetime.fromisoformat(expires) - datetime.now(timezone.utc)).total_seconds()))
    error = QuestError("REQUEST_IN_PROGRESS", 409, "A local generation request is already running. Retry the same intent later.", True)
    error.retry_after = seconds
    return error


def find_intent(session, key: str, operation: str, target: str, digest: str) -> GenerationIntent | None:
    if session.get(TransitionReceipt, key):
        raise conflict()
    intent = session.get(GenerationIntent, key)
    if intent and (intent.operation, intent.target_id, intent.request_hash) != (operation, target, digest):
        raise conflict()
    return intent


def succeed(intent: GenerationIntent, resource_id: str) -> None:
    intent.state, intent.resource_id, intent.lease_expires_at, intent.error_code = "succeeded", resource_id, None, None
    intent.updated_at = utc_text()


def new_receipt(key: str, operation: str, target: str, digest: str, resource: str) -> GenerationIntent:
    now = utc_text()
    return GenerationIntent(key=key, profile_id=1, operation=operation, target_id=target, request_hash=digest,
                            state="succeeded", attempt_number=1, lease_expires_at=None, resource_id=resource,
                            error_code=None, created_at=now, updated_at=now)


@dataclass(frozen=True)
class Reservation:
    key: str
    attempt: int
    context: QuestlineContext
    grounding: GroundingContext


@dataclass(frozen=True)
class PipelineResult:
    view: QuestlineView
    replayed: bool
    generation: QuestPlanResult | None = None
    review: SemanticReview | None = None
    latency_seconds: float = 0


class CheckInService:
    def __init__(self, quests: QuestService):
        self.quests = quests
        self.database = quests.database

    def get(self, check_in_id: str) -> CheckInView:
        with unit_of_work(self.database) as session:
            return check_in_view(get_check_in(session, valid_id(check_in_id)))

    def submit(self, body: CheckInStart | CheckInAnswer, key: str) -> tuple[CheckInView, bool]:
        key = valid_id(key)
        operation = "check_in_start" if isinstance(body, CheckInStart) else "check_in_answer"
        target = key if operation == "check_in_start" else str(body.check_in_id)
        digest = request_hash(operation, target, body.model_dump(mode="json"))
        with unit_of_work(self.database, write=True) as session:
            receipt = find_intent(session, key, operation, target, digest)
            if receipt:
                return check_in_view(get_check_in(session, receipt.resource_id)), True
            if isinstance(body, CheckInStart):
                context = QuestlineContext.model_validate(body.model_dump(exclude={"mode"}))
                question = clarification_question(context)
                now = utc_text()
                check_in = CheckIn(id=str(uuid4()), profile_id=1, goal=context.goal, **context_values(context),
                                   status="needs_follow_up" if question else "ready", revision=1,
                                   summary=None if question else summary_for(context.goal, None), follow_up_question=question,
                                   follow_up_answer=None, follow_up_count=1 if question else 0, questline_id=None,
                                   created_at=now, updated_at=now)
                session.add(check_in)
            else:
                check_in = get_check_in(session, str(body.check_in_id))
                if check_in.status != "needs_follow_up":
                    raise QuestError("INVALID_STATE", 409, "This check-in is not waiting for an answer.")
                if check_in.revision != body.expected_revision:
                    raise QuestError("STALE_REVISION", 409, "The check-in changed. Reload and try again.", True,
                                     {"current_revision": check_in.revision})
                validate_answer(body.answer)
                check_in.follow_up_answer = body.answer
                check_in.summary = summary_for(check_in.goal, body.answer)
                check_in.status, check_in.updated_at = "ready", utc_text()
                check_in.revision += 1
            session.flush()
            session.add(new_receipt(key, operation, target, digest, check_in.id))
            session.flush()
            result = check_in_view(check_in)
        return result, False

    def reserve(self, operation: str, target: str, body: GenerateQuestlineRequest | ReplanRequest,
                key: str) -> Reservation | QuestlineView:
        key, target = valid_id(key), valid_id(target)
        digest = request_hash(operation, target, body.model_dump(mode="json", exclude_unset=True))
        with unit_of_work(self.database, write=True) as session:
            intent = find_intent(session, key, operation, target, digest)
            if intent and intent.state == "succeeded":
                return public_view(session, get_line(session, intent.resource_id))
            now = utc_text()
            pending = session.scalar(select(GenerationIntent).where(GenerationIntent.operation == operation,
                                      GenerationIntent.target_id == target, GenerationIntent.state == "pending"))
            if pending:
                if pending.lease_expires_at > now:
                    raise in_progress(pending.lease_expires_at)
                pending.state, pending.lease_expires_at, pending.error_code, pending.updated_at = "failed", None, "REQUEST_INTERRUPTED", now
                session.flush()
            if operation == "generate":
                check_in = get_check_in(session, target)
                if check_in.status == "consumed":
                    raise QuestError("CHECK_IN_ALREADY_USED", 409, "This check-in already has a questline. Retrieve its saved state.")
                if check_in.status != "ready":
                    raise QuestError("CHECK_IN_NOT_READY", 409, "Answer the saved clarification before generating.")
                if check_in.revision != body.expected_check_in_revision:
                    raise QuestError("STALE_REVISION", 409, "The check-in changed. Reload and try again.", True,
                                     {"current_revision": check_in.revision})
                context = check_in_context(check_in)
                grounding = GroundingContext(summary=check_in.summary, clarification_answer=check_in.follow_up_answer,
                                             contextual_notes=context.contextual_notes)
            else:
                line = get_line(session, target)
                if line.status != "active":
                    raise QuestError("QUESTLINE_PAUSED" if line.status == "paused" else "INVALID_STATE", 409,
                                     "Only active unfinished questlines can be replanned.")
                check_revision(line, body.expected_revision)
                context = QuestlineContext(goal=line.goal, available_minutes=body.available_minutes, energy=body.energy,
                    deadline=body.deadline if "deadline" in body.model_fields_set else line.deadline,
                    contextual_notes=body.contextual_notes if "contextual_notes" in body.model_fields_set else line.contextual_notes)
                check_in = session.scalar(select(CheckIn).where(CheckIn.questline_id == line.id))
                completed = session.scalars(select(Quest).where(Quest.questline_id == line.id, Quest.status == "completed").order_by(Quest.position))
                grounding = GroundingContext(summary=line.check_in_summary, clarification_answer=check_in.follow_up_answer if check_in else None,
                    contextual_notes=context.contextual_notes, change_reason=body.reason, completed=[CompletedMilestone(title=q.title, action=q.action,
                                                                                           completion_criteria=q.completion_criteria) for q in completed])
                if len(grounding.completed) >= 6:
                    raise QuestError("INVALID_STATE", 409, "Completed history already uses six stages. Continue the saved remaining work; replanning cannot discard completed stages.")
            if intent is None:
                intent = GenerationIntent(key=key, profile_id=1, operation=operation, target_id=target, request_hash=digest,
                                          attempt_number=1, created_at=now)
                session.add(intent)
            else:
                intent.attempt_number += 1
            intent.state, intent.resource_id, intent.error_code, intent.updated_at = "pending", None, None, now
            intent.lease_expires_at = utc_text(datetime.now(timezone.utc) + timedelta(seconds=LEASE_SECONDS))
            session.flush()
            result = Reservation(key, intent.attempt_number, context, grounding)
        return result

    def fail(self, reservation: Reservation, code: str) -> None:
        with unit_of_work(self.database, write=True) as session:
            intent = session.get(GenerationIntent, reservation.key)
            if intent and intent.state == "pending" and intent.attempt_number == reservation.attempt:
                intent.state, intent.lease_expires_at, intent.resource_id, intent.error_code = "failed", None, None, code
                intent.updated_at = utc_text()

    def commit(self, reservation: Reservation, body: GenerateQuestlineRequest | ReplanRequest, generation: QuestPlanResult,
               model: str) -> QuestlineView:
        with unit_of_work(self.database, write=True) as session:
            intent = session.get(GenerationIntent, reservation.key)
            if intent is None or intent.state != "pending" or intent.attempt_number != reservation.attempt or intent.lease_expires_at <= utc_text():
                raise QuestError("REQUEST_INTERRUPTED", 503, "This generation intent expired or was replaced. Retry explicitly.", True)
            if intent.operation == "generate":
                check_in = get_check_in(session, intent.target_id)
                if check_in.status != "ready" or check_in.revision != body.expected_check_in_revision:
                    raise QuestError("STALE_REVISION", 409, "The check-in changed before generation could be saved.", True)
                result = self.quests.create_questline(reservation.context, generation.plan, summary=reservation.grounding.summary,
                                                    model_tag=model, prompt_version=QUALITY_VERSION, _session=session)
                check_in.questline_id, check_in.status, check_in.updated_at = result.id, "consumed", utc_text()
                check_in.revision += 1
            else:
                result = self.quests.replace_unfinished(intent.target_id, body.expected_revision, generation.plan, reservation.context,
                    summary=reservation.grounding.summary, reason=body.reason, model_tag=model, prompt_version=QUALITY_VERSION, _session=session)
            succeed(intent, result.id)
            session.flush()
        return result

    async def generate(self, body: GenerateQuestlineRequest | ReplanRequest, key: str, ollama: OllamaClient,
                       *, line_id: str | None = None) -> PipelineResult:
        started = perf_counter()
        operation, target = ("replan", line_id) if line_id is not None else ("generate", str(body.check_in_id))
        reservation = await run_in_threadpool(self.reserve, operation, target, body, key)
        if isinstance(reservation, QuestlineView):
            return PipelineResult(reservation, True, latency_seconds=perf_counter() - started)
        generation, review = None, None
        try:
            try:
                require_local_url(ollama.client.base_url)
            except ValueError:
                raise QuestError("OLLAMA_UNAVAILABLE", 503, "Configure Ollama with a loopback URL and restart the backend.") from None
            remaining = PIPELINE_SECONDS - (perf_counter() - started)
            if remaining <= 0:
                raise QuestError("AI_TIMEOUT", 504, "Local generation exceeded its budget. Retry explicitly.", True)

            async def check_candidate(plan, remaining_budget: float) -> CandidateAssessment:
                issues, warnings = essential_checks(plan, reservation.context, reservation.grounding)
                # No self-approval call. Warnings stay internal diagnostic codes;
                # only essential failures consume the existing correction budget.
                return CandidateAssessment(plan, issues, stage="essential_constraints", warnings=warnings)

            generation = await ollama.generate_quest_plan(reservation.context, grounding=reservation.grounding,
                            replacement=operation == "replan", timeout=remaining, attempt_timeout=60,
                            candidate_check=check_candidate)
            if perf_counter() - started >= PIPELINE_SECONDS:
                raise QuestError("AI_TIMEOUT", 504, "Local generation exceeded its budget. Retry explicitly.", True)
            result = await run_in_threadpool(self.commit, reservation, body, generation, ollama.model)
            return PipelineResult(result, False, generation, review, perf_counter() - started)
        except (QuestError, QuestGenerationError) as exc:
            code = exc.code
            try:
                await run_in_threadpool(self.fail, reservation, code)
            except QuestError:
                pass  # Durable lease expiry still provides recovery if storage is down.
            if isinstance(exc, QuestGenerationError):
                status = 504 if code == "AI_TIMEOUT" else 503 if code in ("OLLAMA_UNAVAILABLE", "MODEL_UNAVAILABLE") else 502
                if code == "AI_REVIEW_UNCERTAIN":
                    error = QuestError(code, 502, "The local model could not confidently verify its candidate after one correction. Your check-in is saved; retry generation.", True,
                                       {"codes": ["uncertain_review"]})
                elif code == "AI_SEMANTIC_REJECTED":
                    error = reject_semantics(exc.quality_codes)
                else:
                    error = QuestError(code, status, str(exc), True)
                generation = getattr(exc, "generation_result", generation)
                error.generation_error = exc
            else:
                error = exc
            # Internal evidence only; public handler serializes safe code/message/details.
            error.generation_result, error.review_result = generation, review
            raise error from None
        except BaseException:
            try:
                await asyncio.shield(run_in_threadpool(self.fail, reservation, "REQUEST_INTERRUPTED"))
            except QuestError:
                pass
            raise
