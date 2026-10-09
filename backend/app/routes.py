from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .ollama import OllamaClient, OllamaError
from .schemas import AIStatus, GenerateRequest, GenerateResponse
from .errors import QuestError

router = APIRouter(prefix="/api")


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


OllamaDependency = Annotated[OllamaClient, Depends(get_ollama)]


@router.get("/health")
def health(request: Request) -> JSONResponse:
    available = getattr(request.app.state, "database_available", False)
    if available:
        try:
            request.app.state.quests.get_profile()
        except QuestError:
            available = False
    return JSONResponse(status_code=200 if available else 503, headers={"Cache-Control": "no-store"}, content={
        "status": "ok" if available else "unavailable", "service": "appbuilders-backend",
        "components": {"database": {"available": available}}})


@router.get("/ai/status", response_model=AIStatus)
async def ai_status(ollama: OllamaDependency) -> AIStatus:
    return await ollama.status()


@router.post("/ai/generate", response_model=GenerateResponse)
async def ai_generate(body: GenerateRequest, ollama: OllamaDependency) -> GenerateResponse:
    try:
        return await ollama.generate(body.prompt)
    except OllamaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
