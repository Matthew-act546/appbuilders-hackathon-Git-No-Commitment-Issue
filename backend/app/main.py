from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import engine
from .ollama import OllamaClient
from .routes import router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ignore proxy environment variables: Ollama traffic stays on its configured host.
    async with httpx.AsyncClient(base_url=str(settings.ollama_base_url).rstrip("/"), trust_env=False) as client:
        app.state.ollama = OllamaClient(client, settings)
        try:
            yield
        finally:
            engine.dispose()


app = FastAPI(title="AppBuilders Hackathon API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
