import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.database import create_sqlite_engine, unit_of_work
from app.errors import QuestError
from app.main import app
from app.models import CheckIn, Completion, GenerationIntent, Profile, Quest, Questline
from app.ollama import OllamaClient, QuestPlanResult
from app.quality import clarification_question, deterministic_issues
from app.schema import SCHEMA_VERSION, expected_catalog, initialize_database
from app.schemas import (CheckInAnswer, CheckInStart, GenerateQuestlineRequest, GroundingContext,
                         QuestlineContext, QuestPlan, ReplacementPlan, ReplanRequest, SemanticReview)
from app.services.check_in import CheckInService
from app.services.quests import QuestService, utc_text

SPECIFIC = "Write three unit tests for my FastAPI login endpoint"


def plan_data():
    return {"quests": [
        {"title": "Inspect the endpoint", "action": "Read the local FastAPI login endpoint and list three expected responses.",
         "completion_criteria": "A written list contains the three expected responses.", "estimated_minutes": 5, "difficulty": "easy"},
        {"title": "Write the tests", "action": "Write three unit tests for the FastAPI login endpoint using the existing local test suite.",
         "completion_criteria": "The test file contains three tests with assertions for the listed responses.", "estimated_minutes": 30, "difficulty": "medium"},
        {"title": "Run the tests", "action": "Run the three tests locally and record each result.",
         "completion_criteria": "The saved result lists each test and its pass or fail outcome.", "estimated_minutes": 10, "difficulty": "easy"},
    ]}


def outer(value):
    return {"response": json.dumps(value), "done": True, "done_reason": "stop"}


def approval(**updates):
    return {"acceptable": True, "confidence": "high", "issues": [], **updates}


def start(goal=SPECIFIC, **updates):
    return CheckInStart(mode="start", goal=goal, available_minutes=20, energy="low", **updates)


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "pipeline.db"
        self.url = f"sqlite:///{self.path}"
        self.database = create_sqlite_engine(self.url)
        initialize_database(self.database)
        self.quests = QuestService(self.database)
        self.service = CheckInService(self.quests)
        self.calls = []
        self.clients = []

    async def asyncTearDown(self):
        for client in self.clients:
            await client.aclose()
        self.database.dispose()
        self.directory.cleanup()

    def adapter(self, responses):
        def handler(request):
            payload = json.loads(request.content)
            self.calls.append(payload)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response if isinstance(response, httpx.Response) else httpx.Response(200, json=outer(response))
        client = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
        self.clients.append(client)
        return OllamaClient(client, Settings(_env_file=None))

    def request(self, check_in=None):
        check_in = check_in or self.service.submit(start(), str(uuid4()))[0]
        return GenerateQuestlineRequest(check_in_id=check_in.id, expected_check_in_revision=check_in.revision)

    def count(self, model):
        with unit_of_work(self.database) as session:
            return len(list(session.scalars(select(model))))

    async def assert_error(self, code, coroutine):
        with self.assertRaises(QuestError) as result:
            await coroutine
        self.assertEqual(result.exception.code, code)
        return result.exception

    async def test_specific_goal_generates_persists_and_replays_without_ai(self):
        body = self.request()
        adapter = self.adapter([plan_data(), approval()])
        key = str(uuid4())
        result = await self.service.generate(body, key, adapter)
        self.assertEqual(result.view.progress.remaining_count, 3)
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.count(Quest), 3)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
        check_in = self.service.get(str(body.check_in_id))
        self.assertEqual(check_in.status, "consumed")
        self.assertEqual(check_in.questline_id, result.view.id)
        replay = await self.service.generate(body, key, adapter)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.view.id, result.view.id)
        self.assertEqual(len(self.calls), 1)
        await self.assert_error("CHECK_IN_ALREADY_USED", self.service.generate(body, str(uuid4()), adapter))
        self.assertEqual(self.count(Questline), 1)

    async def test_ambiguous_goal_clarifies_before_any_inference(self):
        for goal in ("Finish my assignment", "Prepare my presentation", "Study for my exam", "Improve my programming skills", "finish it"):
            with self.subTest(goal=goal):
                check_in, _ = self.service.submit(start(goal), str(uuid4()))
                self.assertEqual(check_in.status, "needs_follow_up")
                self.assertTrue(check_in.question)
                await self.assert_error("CHECK_IN_NOT_READY", self.service.generate(self.request(check_in), str(uuid4()), self.adapter([])))
        self.assertFalse(self.calls)
        self.assertEqual(self.count(Questline), 0)

    async def test_answer_preserves_original_goal_and_grounding(self):
        first, _ = self.service.submit(start("Finish my assignment"), str(uuid4()))
        answer = "Write three unit tests for the existing FastAPI login endpoint using local files."
        body = CheckInAnswer(mode="answer", check_in_id=first.id, expected_revision=1, answer=answer)
        ready, _ = self.service.submit(body, str(uuid4()))
        self.assertEqual(ready.context.goal, first.context.goal)
        self.assertEqual(ready.clarification_answer, answer)
        self.assertIsNone(ready.question)
        adapter = self.adapter([plan_data(), approval()])
        await self.service.generate(self.request(ready), str(uuid4()), adapter)
        self.assertIn(answer, self.calls[0]["prompt"])
        self.assertIn(first.context.goal, self.calls[0]["prompt"])
        with unit_of_work(self.database) as session:
            stored = session.get(CheckIn, first.id)
            self.assertEqual(stored.follow_up_question, first.question)
            self.assertEqual(stored.follow_up_count, 1)

    async def test_insufficient_answer_keeps_same_question_and_never_fabricates(self):
        first, _ = self.service.submit(start("Finish my assignment"), str(uuid4()))
        with self.assertRaises(QuestError) as captured:
            self.service.submit(CheckInAnswer(mode="answer", check_in_id=first.id, expected_revision=1, answer="anything"), str(uuid4()))
        self.assertEqual(captured.exception.code, "CLARIFICATION_INSUFFICIENT")
        current = self.service.get(first.id)
        self.assertEqual(current.question, first.question)
        self.assertIsNone(current.clarification_answer)
        self.assertEqual(current.revision, 1)

    async def test_check_in_idempotency_conflicts_and_no_second_answer(self):
        key = str(uuid4())
        first, replayed = self.service.submit(start("Finish my assignment"), key)
        replay, replayed = self.service.submit(start("Finish my assignment"), key)
        self.assertTrue(replayed)
        self.assertEqual(replay.id, first.id)
        with self.assertRaises(QuestError) as captured:
            self.service.submit(start(), key)
        self.assertEqual(captured.exception.code, "IDEMPOTENCY_CONFLICT")
        answer_key = str(uuid4())
        answer = CheckInAnswer(mode="answer", check_in_id=first.id, expected_revision=1, answer="FastAPI login unit tests")
        ready, _ = self.service.submit(answer, answer_key)
        replay, repeated = self.service.submit(answer, answer_key)
        self.assertTrue(repeated)
        self.assertEqual(replay.revision, ready.revision)
        with self.assertRaises(QuestError):
            self.service.submit(answer, str(uuid4()))

    async def test_essential_violations_rejected_but_subjective_findings_are_warnings(self):
        changes = (
            ("action", "Write a Python Hello World calculator instead of the assignment.", "unsupported_assumption"),
            ("action", "Sign up for an online challenge and attend a meetup.", "external_dependency"),
            ("completion_criteria", "Feel confident and understand the material.", "unobservable_criteria"),
            ("action", "Work on it.", "vague_action"),
            ("estimated_minutes", 15, "implausible_estimate"),
            ("difficulty", "hard", "inappropriate_difficulty"),
        )
        for field, value, code in changes:
            with self.subTest(code=code):
                plan = plan_data(); plan["quests"][0][field] = value
                body = self.request()
                if code in {"unsupported_assumption", "external_dependency"}:
                    error = await self.assert_error("AI_SEMANTIC_REJECTED", self.service.generate(body, str(uuid4()), self.adapter([plan, plan])))
                    self.assertIn(code, error.details["codes"])
                    self.assertEqual(self.service.get(str(body.check_in_id)).status, "ready")
                else:
                    result = await self.service.generate(body, str(uuid4()), self.adapter([plan]))
                    self.assertIn(code, result.generation.assessments[0].warnings)
                    self.assertEqual(result.generation.assessments[0].codes, ())
                    self.assertEqual(len(result.generation.attempts), 1)
        self.assertEqual(self.count(Questline), 4)
        self.assertEqual(self.quests.get_profile().total_xp, 0)

    async def test_model_review_is_not_called_for_valid_proposals(self):
        for decision, code in ((approval(acceptable=False, issues=["unrelated"]), "AI_SEMANTIC_REJECTED"),
                               (approval(acceptable=False, confidence="low"), "AI_REVIEW_UNCERTAIN")):
            with patch.object(OllamaClient, "review_quest_plan", side_effect=AssertionError("No subjective approval call")):
                result = await self.service.generate(self.request(), str(uuid4()), self.adapter([plan_data(), decision]))
            self.assertIsNone(result.review)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.count(Questline), 2)

    async def test_invalid_json_retry_and_two_invalid_outputs_do_not_duplicate(self):
        adapter = self.adapter([httpx.Response(200, json={"response": "{", "done": True}), plan_data(), approval()])
        result = await self.service.generate(self.request(), str(uuid4()), adapter)
        self.assertEqual(len(result.generation.attempts), 2)
        self.assertEqual(self.count(Questline), 1)
        await self.assert_error("AI_INVALID_OUTPUT", self.service.generate(self.request(), str(uuid4()), self.adapter([
            httpx.Response(200, json={"response": "{", "done": True}), httpx.Response(200, json={"response": "{", "done": True})])))
        self.assertEqual(self.count(Questline), 1)

    async def test_connection_model_and_timeout_are_recoverable_without_review(self):
        for response, code in ((httpx.ConnectError("private input"), "OLLAMA_UNAVAILABLE"),
                               (httpx.ReadTimeout("private input"), "AI_TIMEOUT"),
                               (httpx.Response(404, json={"error": "private model"}), "MODEL_UNAVAILABLE")):
            body, key = self.request(), str(uuid4())
            error = await self.assert_error(code, self.service.generate(body, key, self.adapter([response])))
            self.assertNotIn("private", str(error))
            with unit_of_work(self.database) as session:
                self.assertEqual(session.get(GenerationIntent, key).state, "failed")
            recovered = await self.service.generate(body, key, self.adapter([plan_data(), approval()]))
            self.assertFalse(recovered.replayed)
        body = self.request()
        result = await self.service.generate(body, str(uuid4()), self.adapter([plan_data(), {"acceptable": True}]))
        self.assertIsNone(result.review)
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "consumed")

    async def test_concurrent_generation_uses_one_inference_and_no_write_lock(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def handler(request):
            payload = json.loads(request.content)
            self.calls.append(payload)
            if "quests" in payload["format"].get("properties", {}):
                entered.set()
                await release.wait()
                return httpx.Response(200, json=outer(plan_data()))
            return httpx.Response(200, json=outer(approval()))
        client = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
        self.clients.append(client)
        adapter = OllamaClient(client, Settings(_env_file=None))
        body, key = self.request(), str(uuid4())
        task = asyncio.create_task(self.service.generate(body, key, adapter))
        await asyncio.wait_for(entered.wait(), 5)
        try:
            for duplicate_key in (key, str(uuid4())):
                await self.assert_error("REQUEST_IN_PROGRESS", self.service.generate(body, duplicate_key, adapter))
            other = self.quests.create_questline(QuestlineContext(goal=SPECIFIC, available_minutes=20, energy="low"),
                                                QuestPlan(**plan_data()), summary="Independent line")
            self.assertEqual(self.quests.complete_quest(other.current_quest.id, 1).awarded_xp, 10)
        finally:
            release.set()
        await task
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.count(Questline), 2)  # One explicitly created independent line.

    async def test_expired_crashed_request_can_restart_and_old_worker_is_fenced(self):
        body, key = self.request(), str(uuid4())
        old = self.service.reserve("generate", str(body.check_in_id), body, key)
        with unit_of_work(self.database, write=True) as session:
            session.get(GenerationIntent, key).lease_expires_at = utc_text(datetime.now(timezone.utc) - timedelta(seconds=1))
        self.database.dispose()
        initialize_database(self.database)
        new = self.service.reserve("generate", str(body.check_in_id), body, key)
        self.assertEqual(new.attempt, 2)
        generation = QuestPlanResult(QuestPlan(**plan_data()), (), 1)
        with self.assertRaises(QuestError) as result:
            self.service.commit(old, body, generation, "qwen3:1.7b")
        self.assertEqual(result.exception.code, "REQUEST_INTERRUPTED")
        self.service.fail(old, "AI_TIMEOUT")
        with unit_of_work(self.database) as session:
            self.assertEqual(session.get(GenerationIntent, key).state, "pending")
        saved = self.service.commit(new, body, generation, "qwen3:1.7b")
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.service.get(str(body.check_in_id)).questline_id, saved.id)

    async def test_expired_lease_without_replacement_cannot_commit(self):
        body, key = self.request(), str(uuid4())
        old = self.service.reserve("generate", str(body.check_in_id), body, key)
        with unit_of_work(self.database, write=True) as session:
            session.get(GenerationIntent, key).lease_expires_at = utc_text(datetime.now(timezone.utc) - timedelta(seconds=1))
        with self.assertRaises(QuestError):
            self.service.commit(old, body, QuestPlanResult(QuestPlan(**plan_data()), (), 1), "qwen3:1.7b")
        self.assertEqual(self.count(Questline), 0)

    async def test_generation_key_conflict_does_not_call_ai(self):
        first, second = self.request(), self.request()
        key = str(uuid4())
        await self.service.generate(first, key, self.adapter([plan_data(), approval()]))
        await self.assert_error("IDEMPOTENCY_CONFLICT", self.service.generate(second, key, self.adapter([])))
        self.assertEqual(len(self.calls), 1)

    async def test_pipeline_timeout_after_generation_does_not_save(self):
        body = self.request()
        with patch("app.services.check_in.perf_counter", side_effect=[0, 0, 121]):
            await self.assert_error("AI_TIMEOUT", self.service.generate(body, str(uuid4()), self.adapter([plan_data(), approval()])))
        self.assertEqual(self.count(Questline), 0)
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "ready")

    async def test_cancelled_generation_releases_intent_for_explicit_retry(self):
        entered = asyncio.Event()
        async def handler(request):
            entered.set()
            await asyncio.Event().wait()
        client = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(handler))
        self.clients.append(client)
        body, key = self.request(), str(uuid4())
        task = asyncio.create_task(self.service.generate(body, key, OllamaClient(client, Settings(_env_file=None))))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        with unit_of_work(self.database) as session:
            self.assertEqual(session.get(GenerationIntent, key).state, "failed")
        await self.service.generate(body, key, self.adapter([plan_data(), approval()]))
        self.assertEqual(self.count(Questline), 1)

    async def test_remote_runtime_rejected_without_network_or_losing_context(self):
        body, key = self.request(), str(uuid4())
        def handler(request):
            raise AssertionError("No remote inference is permitted")
        client = httpx.AsyncClient(base_url="https://remote.example", transport=httpx.MockTransport(handler))
        self.clients.append(client)
        error = await self.assert_error("OLLAMA_UNAVAILABLE", self.service.generate(body, key, OllamaClient(client, Settings(_env_file=None))))
        self.assertIn("loopback", str(error))
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "ready")

    async def test_diagnostic_client_also_refuses_remote_inference(self):
        from app.ollama import OllamaError
        def handler(request):
            raise AssertionError("No remote diagnostic request is permitted")
        client = httpx.AsyncClient(base_url="https://remote.example", transport=httpx.MockTransport(handler))
        self.clients.append(client)
        adapter = OllamaClient(client, Settings(_env_file=None))
        with self.assertRaises(OllamaError) as error:
            await adapter.generate("Fictional diagnostic prompt")
        self.assertEqual(error.exception.status_code, 503)
        self.assertFalse((await adapter.status()).available)

    async def test_database_failure_rolls_back_plan_consumption_and_receipt(self):
        body, key = self.request(), str(uuid4())
        def fail(connection, cursor, statement, parameters, execution_context, executemany):
            if statement.startswith("UPDATE generation_intents") and "succeeded" in parameters:
                raise OperationalError(statement, parameters, sqlite3.OperationalError("private SQL"))
        event.listen(self.database, "before_cursor_execute", fail)
        try:
            await self.assert_error("STORAGE_UNAVAILABLE", self.service.generate(body, key, self.adapter([plan_data(), approval()])))
        finally:
            event.remove(self.database, "before_cursor_execute", fail)
        self.assertEqual(self.count(Questline), 0)
        self.assertEqual(self.count(Quest), 0)
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "ready")
        await self.service.generate(body, key, self.adapter([plan_data(), approval()]))
        self.assertEqual(self.count(Questline), 1)

    async def test_replan_preserves_history_xp_and_replays(self):
        initial = await self.service.generate(self.request(), str(uuid4()), self.adapter([plan_data(), approval()]))
        line = self.quests.complete_quest(initial.view.current_quest.id, 1).questline
        history = line.completed_quests[0].model_dump()
        remaining = {"quests": plan_data()["quests"][1:]}
        body = ReplanRequest(expected_revision=line.revision, available_minutes=30, energy="medium", reason="Use the new local test fixtures")
        key = str(uuid4())
        adapter = self.adapter([remaining, approval()])
        result = await self.service.generate(body, key, adapter, line_id=line.id)
        self.assertEqual(result.view.completed_quests[0].model_dump(), history)
        self.assertEqual(self.quests.get_profile().total_xp, 10)
        self.assertEqual(result.view.plan_version, 2)
        self.assertIn(history["action"], self.calls[-1]["prompt"])
        self.assertIn(body.reason, self.calls[-1]["prompt"])
        count = len(self.calls)
        replay = await self.service.generate(body, key, adapter, line_id=line.id)
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.view.plan_version, 2)
        self.assertEqual(len(self.calls), count)

    async def test_stale_replan_discards_generated_result(self):
        initial = await self.service.generate(self.request(), str(uuid4()), self.adapter([plan_data(), approval()]))
        line = initial.view
        body = ReplanRequest(expected_revision=1, available_minutes=20, energy="low")
        key = str(uuid4())
        reservation = self.service.reserve("replan", line.id, body, key)
        current = self.quests.complete_quest(line.current_quest.id, 1).questline
        generation = QuestPlanResult(ReplacementPlan(**{"quests": plan_data()["quests"][2:]}), (), 1)
        with self.assertRaises(QuestError) as result:
            self.service.commit(reservation, body, generation, "qwen3:1.7b")
        self.assertEqual(result.exception.code, "STALE_REVISION")
        self.assertEqual(self.quests.get_questline(line.id).model_dump(), current.model_dump())
        self.assertEqual(self.quests.get_profile().total_xp, 10)

    async def test_replan_omitted_fields_preserve_and_null_clears(self):
        check_in, _ = self.service.submit(start(deadline="2026-10-10T10:00:00+08:00", contextual_notes="Use existing local files"), str(uuid4()))
        initial = await self.service.generate(self.request(check_in), str(uuid4()), self.adapter([plan_data(), approval()]))
        line = initial.view
        base = {"expected_revision": line.revision, "available_minutes": 20, "energy": "low"}
        first = self.service.reserve("replan", line.id, ReplanRequest(**base), str(uuid4()))
        self.assertIsNotNone(first.context.deadline)
        self.assertEqual(first.context.contextual_notes, "Use existing local files")
        self.service.fail(first, "AI_TIMEOUT")
        second = self.service.reserve("replan", line.id, ReplanRequest(**base, deadline=None, contextual_notes=None), str(uuid4()))
        self.assertIsNone(second.context.deadline)
        self.assertIsNone(second.context.contextual_notes)

    async def test_restart_restores_context_and_successful_generation_replay(self):
        body, key = self.request(), str(uuid4())
        initial = await self.service.generate(body, key, self.adapter([plan_data(), approval()]))
        self.database.dispose()
        code = """import json,sys
from app.database import create_sqlite_engine
from app.schema import initialize_database
from app.services.quests import QuestService
from app.services.check_in import CheckInService
from app.schemas import GenerateQuestlineRequest
engine=create_sqlite_engine(sys.argv[1]);initialize_database(engine);s=CheckInService(QuestService(engine))
body=GenerateQuestlineRequest(check_in_id=sys.argv[2],expected_check_in_revision=1)
v=s.reserve('generate',sys.argv[2],body,sys.argv[3]);print(json.dumps({'id':v.id,'status':s.get(sys.argv[2]).status}));engine.dispose()
"""
        child = subprocess.run([sys.executable, "-c", code, self.url, str(body.check_in_id), key], capture_output=True, text=True, timeout=20)
        self.assertEqual(child.returncode, 0, child.stderr)
        self.assertEqual(json.loads(child.stdout), {"id": initial.view.id, "status": "consumed"})


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = create_sqlite_engine(f"sqlite:///{Path(self.directory.name) / 'v1.db'}")
        self.addCleanup(self.database.dispose)
        with unit_of_work(self.database, write=True) as session:
            for kind, name, sql in sorted(expected_catalog(1), key=lambda row: (row[0] != "table", row[1])):
                session.execute(text(sql))
            now = utc_text()
            session.add(Profile(id=1, total_xp=0, created_at=now, updated_at=now))
            session.execute(text("PRAGMA user_version=1"))
            # Populate synthetic legacy rows with today's service, then remove
            # the optional column to reproduce the exact historical catalog.
            session.execute(text("ALTER TABLE quests ADD COLUMN completion_encouragement VARCHAR"))
        self.quests = QuestService(self.database)
        self.line = self.quests.create_questline(QuestlineContext(goal=SPECIFIC, available_minutes=20, energy="low"),
                                                QuestPlan(**plan_data()), summary="Version-one fixture")
        self.line = self.quests.complete_quest(self.line.current_quest.id, 1).questline
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE quests DROP COLUMN completion_encouragement"))

    def snapshot(self):
        with unit_of_work(self.database) as session:
            return {name: session.execute(text(f"SELECT {', '.join(row[1] for row in session.execute(text(f'PRAGMA table_info({name})')) if row[1] != 'completion_encouragement')} FROM {name} ORDER BY 1")).all()
                    for name in ("profiles", "questlines", "plan_versions", "quests", "completions", "transition_receipts")}

    def test_v1_to_current_preserves_rows_xp_history_and_repeated_startup(self):
        before = self.snapshot()
        initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.quests.get_profile().total_xp, 10)
        self.assertEqual(self.quests.get_questline(self.line.id).model_dump(), self.line.model_dump())
        initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), SCHEMA_VERSION)
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)

    def test_failed_migration_rolls_back_ddl_and_version_without_losing_rows(self):
        before = self.snapshot()
        def fail(connection, cursor, statement, params, execution_context, executemany):
            if "CREATE TABLE generation_intents" in statement:
                raise OperationalError(statement, params, sqlite3.OperationalError("injected migration failure"))
        event.listen(self.database, "before_cursor_execute", fail)
        try:
            with self.assertRaises(QuestError):
                initialize_database(self.database)
        finally:
            event.remove(self.database, "before_cursor_execute", fail)
        self.assertEqual(self.snapshot(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), 1)
            self.assertIsNone(session.scalar(text("SELECT name FROM sqlite_master WHERE name='check_ins'")))
        initialize_database(self.database)

    def test_mismatched_v1_is_rejected_without_mutation(self):
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("DROP INDEX uq_quest_current"))
        before = self.snapshot()
        with self.assertRaises(QuestError):
            initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)


class CheckInAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = create_sqlite_engine(f"sqlite:///{Path(self.directory.name) / 'api.db'}")
        self.replacement = patch("app.main.engine", self.database); self.replacement.start()
        self.lifespan = app.router.lifespan_context(app); await self.lifespan.__aenter__()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.replacement.stop(); self.directory.cleanup()

    async def test_api_start_answer_retrieve_generate_and_filtered_replan(self):
        upstream = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=outer(
            approval() if "anyOf" in json.loads(r.content)["format"] or "acceptable" in json.loads(r.content)["format"].get("properties", {}) else plan_data()))))
        async with upstream:
            app.state.ollama = OllamaClient(upstream, Settings(_env_file=None))
            response = await self.client.post("/api/check-in", json=start("Finish my assignment").model_dump(mode="json"), headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 201, response.text)
            first = response.json()
            response = await self.client.post("/api/check-in", json={"mode": "answer", "check_in_id": first["id"], "expected_revision": 1,
                "answer": "Write three unit tests for the existing FastAPI login endpoint"}, headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual((await self.client.get(f"/api/check-in/{first['id']}")).json()["status"], "ready")
            key = str(uuid4())
            response = await self.client.post("/api/questlines", json={"check_in_id": first["id"], "expected_check_in_revision": 2}, headers={"Idempotency-Key": key})
            self.assertEqual(response.status_code, 201, response.text)
            line = response.json()
            self.assertNotIn(plan_data()["quests"][1]["action"], response.text)
            self.assertEqual(response.headers["cache-control"], "no-store")
            repeated = await self.client.post("/api/questlines", json={"check_in_id": first["id"], "expected_check_in_revision": 2}, headers={"Idempotency-Key": key})
            self.assertEqual(repeated.status_code, 200)
            self.assertEqual(repeated.json()["id"], line["id"])
            response = await self.client.post(f"/api/questlines/{line['id']}/replan", json={"expected_revision": 1, "available_minutes": 20, "energy": "low"}, headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["plan_version"], 2)
            self.assertNotIn(plan_data()["quests"][1]["action"], response.text)
            self.assertNotIn(line["current_quest"]["id"], response.text)

    async def test_api_strict_dates_lengths_uuid_and_private_validation_errors(self):
        valid = start().model_dump(mode="json")
        for update in ({"available_minutes": True}, {"available_minutes": "20"}, {"energy": "tired"},
                       {"goal": " "}, {"goal": "x" * 4001}, {"deadline": "2026-10-09T10:00:00"},
                       {"deadline": 123}, {"unknown": "PRIVATE_SENTINEL"}):
            response = await self.client.post("/api/check-in", json={**valid, **update}, headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertNotIn("PRIVATE_SENTINEL", response.text)
        valid["deadline"] = "2026-10-10T10:00:00+08:00"
        response = await self.client.post("/api/check-in", json=valid, headers={"Idempotency-Key": str(uuid4())})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["context"]["deadline"], "2026-10-10T02:00:00Z")
        self.assertEqual((await self.client.get("/api/check-in/not-uuid")).status_code, 422)

    async def test_api_pending_error_has_retry_after_and_no_plan_contents(self):
        service = CheckInService(app.state.quests)
        first, _ = service.submit(start(), str(uuid4()))
        body = GenerateQuestlineRequest(check_in_id=first.id, expected_check_in_revision=1)
        key = str(uuid4()); service.reserve("generate", first.id, body, key)
        response = await self.client.post("/api/questlines", json=body.model_dump(mode="json"), headers={"Idempotency-Key": key})
        self.assertEqual(response.status_code, 409)
        self.assertIn("retry-after", response.headers)
        self.assertEqual(response.json()["error"]["code"], "REQUEST_IN_PROGRESS")


class PolicyTests(unittest.TestCase):
    def test_sql_only_plan_cannot_replace_requested_explanation(self):
        ctx = QuestlineContext(goal="Draft a one-page explanation of SQLite transactions", available_minutes=20, energy="low")
        raw = plan_data()
        for i, quest in enumerate(raw["quests"]):
            quest.update(title=f"Transaction example {i}", action=f"Write SQLite transaction example number {i} into a local file.",
                         completion_criteria=f"A saved file contains SQLite transaction example {i}.")
        self.assertIn("unrelated", deterministic_issues(QuestPlan(**raw), ctx, GroundingContext(summary=ctx.goal)))
    def test_literal_counts_existing_inputs_and_http_claims_rejected(self):
        ctx = QuestlineContext(goal=SPECIFIC, available_minutes=20, energy="low")
        grounding = GroundingContext(summary=SPECIFIC)
        raw = plan_data()
        raw["quests"][1]["action"] = "Write two unit tests for the existing FastAPI login endpoint."
        raw["quests"][1]["completion_criteria"] = "Two tests are written and pass."
        self.assertIn("duplicate_or_contradiction", deterministic_issues(QuestPlan(**raw), ctx, grounding))
        raw = plan_data(); raw["quests"][1]["action"] += " Assert a 400 BAD REQUEST response."
        self.assertIn("unsupported_assumption", deterministic_issues(QuestPlan(**raw), ctx, grounding))
        raw = plan_data(); raw["quests"][0]["action"] = "Create a new local list of three elements."
        ctx = QuestlineContext(goal="Practice Python list comprehensions using existing example lists", available_minutes=20, energy="low")
        self.assertIn("unsupported_assumption", deterministic_issues(QuestPlan(**raw), ctx, GroundingContext(summary=ctx.goal)))
    def test_specific_goals_do_not_need_unnecessary_questions(self):
        for goal in (SPECIFIC, "Prepare for an Algorithms and Complexity exam", "Draft slides about local SQLite transactions", "Implement the binary search function for my assignment"):
            self.assertIsNone(clarification_question(start(goal)))

    def test_review_strict_and_low_confidence_cannot_be_accepted(self):
        from pydantic import ValidationError
        for raw in (approval(confidence="low"), approval(issues=["unrelated"]), approval(acceptable="true"), {**approval(), "xp": 100}):
            with self.assertRaises(ValidationError):
                SemanticReview(**raw)

    def test_clinical_requests_refused_without_ai(self):
        with self.assertRaises(QuestError) as error:
            clarification_question(start("Diagnose my depression and prescribe treatment"))
        self.assertEqual(error.exception.code, "UNSUPPORTED_REQUEST")
