from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from .ollama import OllamaClient, OllamaError
from .schemas import AIStatus, GenerateRequest, GenerateResponse

router = APIRouter(prefix="/api")


def get_ollama(request: Request) -> OllamaClient:
    return request.app.state.ollama


OllamaDependency = Annotated[OllamaClient, Depends(get_ollama)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "appbuilders-backend"}


@router.get("/ai/status", response_model=AIStatus)
async def ai_status(ollama: OllamaDependency) -> AIStatus:
    return await ollama.status()


@router.post("/ai/generate", response_model=GenerateResponse)
async def ai_generate(body: GenerateRequest, ollama: OllamaDependency) -> GenerateResponse:
    try:
        return await ollama.generate(body.prompt)
    except OllamaError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
