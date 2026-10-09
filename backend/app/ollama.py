import asyncio
from typing import Any

import httpx

from .config import Settings
from .schemas import AIStatus, GenerateResponse


class OllamaError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


class OllamaClient:
    def __init__(self, client: httpx.AsyncClient, settings: Settings):
        self.client = client
        self.model = settings.ollama_model

    async def _request(self, method: str, path: str, timeout: float, **kwargs: Any) -> dict:
        try:
            async with asyncio.timeout(timeout):
                response = await self.client.request(method, path, timeout=timeout, **kwargs)
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise OllamaError("Ollama timed out. Retry or select the smaller backup model.", 504) from exc
        except httpx.RequestError as exc:
            raise OllamaError("Cannot connect to Ollama. Start Ollama and check OLLAMA_BASE_URL.") from exc
        if response.status_code == 404 and path == "/api/generate":
            raise OllamaError(f"Model '{self.model}' is unavailable. Install it separately or change OLLAMA_MODEL.")
        if response.is_error:
            raise OllamaError(f"Ollama returned HTTP {response.status_code}.", 502)
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaError("Ollama returned invalid JSON.", 502) from exc
        if not isinstance(data, dict) or "error" in data:
            raise OllamaError("Ollama returned an unexpected response.", 502)
        return data

    async def status(self) -> AIStatus:
        try:
            data = await self._request("GET", "/api/tags", 5)
        except OllamaError as exc:
            return AIStatus(available=False, server_available=False, model_available=False,
                            model=self.model, message=str(exc))
        models = data.get("models")
        if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
            return AIStatus(available=False, server_available=True, model_available=False,
                            model=self.model, message="Ollama returned an invalid model list.")
        name = self.model if ":" in self.model else f"{self.model}:latest"
        available = any(model.get("name") == name or model.get("model") == name for model in models)
        return AIStatus(
            available=available, server_available=True, model_available=available,
            model=self.model,
            message="Ollama is reachable and the model is installed." if available
            else "Ollama is reachable, but the configured model is not installed. Install it separately or select the backup.",
        )

    async def generate(self, prompt: str) -> GenerateResponse:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        # Keep the small Qwen3 model's output focused on the answer.
        if self.model.startswith("qwen3:"):
            payload["think"] = False
        data = await self._request("POST", "/api/generate", 120, json=payload)
        if not isinstance(data.get("response"), str):
            raise OllamaError("Ollama returned no valid generated text.", 502)
        return GenerateResponse(model=self.model, response=data["response"])
