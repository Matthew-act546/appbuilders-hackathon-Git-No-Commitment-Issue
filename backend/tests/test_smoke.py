import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import Base, create_sqlite_engine, get_session
from app.main import app
from app.ollama import OllamaClient


class TemporaryDatabase:
    def setUp(self):
        database = create_sqlite_engine("sqlite:///:memory:")
        replacement = patch("app.main.engine", database)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.addCleanup(database.dispose)


class SmokeTests(TemporaryDatabase, unittest.IsolatedAsyncioTestCase):
    async def test_startup_health_cors_and_validation(self):
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
                response = await client.get("/api/health")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "ok")
                self.assertEqual((await client.post("/api/ai/generate", json={"prompt": "   "})).status_code, 422)
                self.assertEqual((await client.post("/api/ai/generate", json={"prompt": "a" * 8001})).status_code, 422)
                for origin in ["http://localhost:5173", "http://localhost:4173", "http://127.0.0.1:5173", "http://127.0.0.1:4173"]:
                    with self.subTest(origin=origin):
                        response = await client.options("/api/ai/generate", headers={
                            "Origin": origin, "Access-Control-Request-Method": "POST",
                            "Access-Control-Request-Headers": "content-type",
                        })
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.headers["access-control-allow-origin"], origin)
                response = await client.get("/api/health", headers={"Origin": "https://untrusted.example"})
                self.assertNotIn("access-control-allow-origin", response.headers)

    def test_settings_and_empty_database(self):
        with patch.dict("os.environ", {
            "OLLAMA_BASE_URL": "http://127.0.0.1:11435",
            "OLLAMA_MODEL": "qwen2.5:1.5b",
            "DATABASE_URL": "sqlite:///:memory:",
            "CORS_ORIGINS": '["http://localhost:9999"]',
        }):
            settings = Settings(_env_file=None)
        self.assertEqual(settings.ollama_model, "qwen2.5:1.5b")
        self.assertEqual(str(settings.ollama_base_url), "http://127.0.0.1:11435/")
        self.assertEqual(settings.cors_origins, ["http://localhost:9999"])
        self.assertEqual(settings.database_url, "sqlite:///:memory:")
        self.assertEqual(set(Base.metadata.tables), {"profiles", "questlines", "plan_versions", "quests", "completions", "transition_receipts"})
        engine = create_engine("sqlite:///:memory:")
        with Session(engine) as session:
            with patch("app.database.SessionLocal", return_value=session):
                dependency = get_session()
                self.assertEqual(next(dependency).scalar(text("SELECT 1")), 1)
                dependency.close()
        self.assertEqual(inspect(engine).get_table_names(), [])
        engine.dispose()


class OllamaRouteTests(TemporaryDatabase, unittest.IsolatedAsyncioTestCase):
    async def call(self, handler, path, body=None):
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://ollama.test") as upstream:
                app.state.ollama = OllamaClient(upstream, Settings(_env_file=None))
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
                    return await client.get(path) if body is None else await client.post(path, json=body)

    async def test_model_ready_and_missing(self):
        for models, expected in [([{"name": "qwen3:1.7b"}], True), ([{"name": "qwen2.5:1.5b"}], False)]:
            response = await self.call(lambda request: httpx.Response(200, json={"models": models}), "/api/ai/status")
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["server_available"])
            self.assertEqual(response.json()["available"], expected)
            self.assertEqual(response.json()["model_available"], expected)

    async def test_generation_uses_configured_model_without_streaming(self):
        import json

        def handler(request):
            self.assertEqual(request.url.path, "/api/generate")
            payload = json.loads(request.content)
            self.assertEqual(payload["model"], "qwen3:1.7b")
            self.assertEqual(payload["prompt"], "Hello")
            self.assertFalse(payload["stream"])
            return httpx.Response(200, json={"response": "Local answer", "done": True})

        response = await self.call(handler, "/api/ai/generate", {"prompt": " Hello "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"model": "qwen3:1.7b", "response": "Local answer"})

    async def test_connection_and_timeout_errors(self):
        for exception, expected in [(httpx.ConnectError, 503), (httpx.ReadTimeout, 504)]:
            def handler(request):
                raise exception("Simulated upstream failure", request=request)

            response = await self.call(handler, "/api/ai/generate", {"prompt": "Hi"})
            self.assertEqual(response.status_code, expected)
            self.assertIsInstance(response.json()["detail"], str)
            response = await self.call(handler, "/api/ai/status")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["available"])
            self.assertFalse(response.json()["server_available"])

    async def test_upstream_errors_and_malformed_responses(self):
        for upstream, expected in [
            (httpx.Response(404, json={"error": "model not found"}), 503),
            (httpx.Response(500, json={"error": "failed"}), 502),
            (httpx.Response(200, text="not JSON"), 502),
            (httpx.Response(200, json={"response": 123}), 502),
        ]:
            response = await self.call(lambda request: upstream, "/api/ai/generate", {"prompt": "Hi"})
            self.assertEqual(response.status_code, expected)


if __name__ == "__main__":
    unittest.main()
