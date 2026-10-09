from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from uuid import uuid4

from .config import get_settings
from .database import engine
from .ollama import OllamaClient
from .routes import router
from .quest_routes import router as quest_router
from .errors import QuestError
from .schema import initialize_database
from .services.quests import QuestService

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.quests = QuestService(engine)
    try:
        initialize_database(engine)
        app.state.database_available = True
    except QuestError:
        # Keep diagnostics reachable; never reset a private/unknown database.
        app.state.database_available = False
    # Ignore proxy environment variables: Ollama traffic stays on its configured host.
    async with httpx.AsyncClient(base_url=str(settings.ollama_base_url).rstrip("/"), trust_env=False) as client:
        app.state.ollama = OllamaClient(client, settings)
        try:
            yield
        finally:
            engine.dispose()


app = FastAPI(title="Local AI Quest Companion API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Idempotency-Key"],
)
app.include_router(router)
app.include_router(quest_router)


@app.exception_handler(QuestError)
async def quest_error(request, exc: QuestError):
    return JSONResponse(status_code=exc.status_code, headers={"Cache-Control": "no-store"}, content={
        "error": {"code": exc.code, "message": str(exc), "retryable": exc.retryable,
                  "request_id": getattr(request.state, "product_request_id", str(uuid4())), "details": exc.details}})


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc: RequestValidationError):
    if hasattr(request.state, "product_request_id"):
        return await quest_error(request, QuestError("VALIDATION_ERROR", 422, "Request validation failed.",
                                 details={"codes": sorted({error["type"] for error in exc.errors()})}))
    return await request_validation_exception_handler(request, exc)
