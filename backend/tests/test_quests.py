import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from pydantic import ValidationError
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError

from app.database import create_sqlite_engine, unit_of_work
from app.errors import QuestError
from app.main import app
from app.models import Completion, Profile, Quest, Questline, PlanVersion, TransitionReceipt
from app.schema import initialize_database
from app.schemas import QuestlineContext, QuestPlan, ReplacementPlan
from app.services.quests import QuestService, utc_text


def proposal(count=3, prefix="Initial", difficulties=("easy", "medium", "hard")):
    return {"quests": [{"title": f"{prefix} quest {i}", "action": f"{prefix} local artifact action {i}",
                       "completion_criteria": f"{prefix} observable result {i}", "estimated_minutes": 5,
                       "difficulty": difficulties[i % len(difficulties)], "hint": f"{prefix} hint {i}"}
                      for i in range(count)]}


def context(**changes):
    return QuestlineContext(goal="Fictional local deliverable", available_minutes=20, energy="low", **changes)


class QuestEngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "quests.db"
        self.url = f"sqlite:///{self.path}"
        self.database = create_sqlite_engine(self.url)
        self.addCleanup(self.database.dispose)
        initialize_database(self.database)
        self.service = QuestService(self.database)

    def create(self, **changes):
        return self.service.create_questline(context(), QuestPlan(**proposal(**changes)), summary="Fictional summary")

    def rows(self, model):
        with unit_of_work(self.database) as session:
            return [dict(row) for row in session.execute(select(model.__table__)).mappings()]

    def snapshot(self):
        return {table.name: self.rows(model) for table, model in [
            (Profile.__table__, Profile), (Questline.__table__, Questline), (PlanVersion.__table__, PlanVersion),
            (Quest.__table__, Quest), (Completion.__table__, Completion), (TransitionReceipt.__table__, TransitionReceipt)]}

    def assert_error(self, code, operation):
        with self.assertRaises(QuestError) as captured:
            operation()
        self.assertEqual(captured.exception.code, code)
        return captured.exception

    def test_fresh_and_repeat_bootstrap_profile_wal_and_connection_pragmas(self):
        self.assertEqual(self.service.get_profile().model_dump(), {"id": 1, "total_xp": 0, "level": 1})
        before = self.snapshot()
        initialize_database(self.database)
        self.assertEqual(before, self.snapshot())
        for _ in range(2):
            with self.database.connect() as connection:
                self.assertEqual(connection.scalar(text("PRAGMA foreign_keys")), 1)
                self.assertEqual(connection.scalar(text("PRAGMA synchronous")), 2)
                self.assertEqual(connection.scalar(text("PRAGMA busy_timeout")), 5000)
                self.assertEqual(connection.scalar(text("PRAGMA journal_mode")), "wal")
                self.assertEqual(connection.scalar(text("PRAGMA user_version")), 1)
            self.database.dispose()

    def test_initial_creation_and_multiple_lines_have_one_current_each(self):
        first, second = self.create(), self.create()
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.progress.model_dump(), {"completed_count": 0, "remaining_count": 3, "total_count": 3})
        self.assertEqual((first.revision, first.plan_version, first.current_quest.order), (1, 1, 1))
        self.assertEqual([q["status"] for q in self.rows(Quest)], ["active", "locked", "locked"] * 2)
        self.assertEqual(self.service.get_profile().total_xp, 0)
        self.assertEqual(len(self.rows(PlanVersion)), 2)

    def test_locked_content_and_ids_are_absent_from_detail_and_list(self):
        line = self.create()
        hidden = [q for q in self.rows(Quest) if q["status"] == "locked"]
        payload = self.service.get_questline(line.id).model_dump_json() + self.service.list_questlines().model_dump_json()
        for quest in hidden:
            for name in ("id", "title", "action", "completion_criteria", "hint"):
                self.assertNotIn(quest[name], payload)
            self.assert_error("QUEST_NOT_FOUND", lambda: self.service.complete_quest(quest["id"], 1))
        self.assertNotIn("current_quest", self.service.list_questlines().model_dump_json())

    def test_sequential_rewards_duplicate_and_final_completion(self):
        line = self.create()
        for index, reward in enumerate((10, 20, 30)):
            quest_id = line.current_quest.id
            old_revision = line.revision
            result = self.service.complete_quest(quest_id, old_revision)
            self.assertEqual(result.awarded_xp, reward)
            line = result.questline
            self.assertEqual(line.progress.completed_count, index + 1)
            self.assertEqual(line.progress.remaining_count, 2 - index)
            before = self.snapshot()
            repeat = self.service.complete_quest(quest_id, old_revision)
            self.assertEqual((repeat.outcome, repeat.awarded_xp), ("already_completed", 0))
            self.assertEqual(before, self.snapshot())
        self.assertEqual(line.status, "completed")
        self.assertIsNone(line.current_quest)
        self.assertEqual(self.service.get_profile().total_xp, 60)
        self.assertEqual(len(self.rows(Completion)), 3)
        self.assert_error("INVALID_STATE", lambda: self.service.set_paused(line.id, line.revision, paused=True, idempotency_key=str(uuid4())))

    def test_level_boundaries_are_integer_arithmetic(self):
        for xp, level in ((0, 1), (90, 1), (100, 2), (110, 2), (200, 3)):
            with unit_of_work(self.database, write=True) as session:
                session.get(Profile, 1).total_xp = xp
            self.assertEqual(self.service.get_profile().level, level)
        # Independent fixture, not an application XP setter; restore consistency.
        with unit_of_work(self.database, write=True) as session:
            session.get(Profile, 1).total_xp = 0
        for difficulties in (("hard", "hard", "hard"), ("easy", "easy", "easy")):
            line = self.create(difficulties=difficulties)
            while line.current_quest:
                line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        self.assertEqual((self.service.get_profile().total_xp, self.service.get_profile().level), (120, 2))

    def test_stale_completion_does_not_change_state(self):
        line = self.create()
        before = self.snapshot()
        error = self.assert_error("STALE_REVISION", lambda: self.service.complete_quest(line.current_quest.id, 2))
        self.assertEqual(error.details, {"current_revision": 1})
        self.assertEqual(before, self.snapshot())

    def test_concurrent_completion_serializes_to_one_award(self):
        line = self.create()
        barrier = Barrier(2)
        def complete():
            barrier.wait(timeout=5)
            return self.service.complete_quest(line.current_quest.id, line.revision)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: complete(), range(2)))
        self.assertEqual(sorted(r.outcome for r in results), ["already_completed", "completed"])
        self.assertEqual(sum(r.awarded_xp for r in results), 10)
        self.assertEqual(len(self.rows(Completion)), 1)
        self.assertEqual(len([q for q in self.rows(Quest) if q["status"] == "active"]), 1)

    def test_concurrent_replan_and_completion_allow_only_one_revision_winner(self):
        line = self.create()
        barrier = Barrier(2)
        replacement = ReplacementPlan(**proposal(1, "Replacement"))
        def operation(replan):
            barrier.wait(timeout=5)
            try:
                if replan:
                    return self.service.replace_unfinished(line.id, 1, replacement, context(), summary="Replacement summary")
                return self.service.complete_quest(line.current_quest.id, 1)
            except QuestError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(operation, (True, False)))
        errors = [r for r in results if isinstance(r, str)]
        self.assertEqual(len(errors), 1)
        self.assertIn(errors[0], ("STALE_REVISION", "QUEST_NOT_FOUND"))
        current = self.service.get_questline(line.id)
        self.assertEqual(current.revision, 2)
        self.assertEqual(self.service.get_profile().total_xp, 10 if current.plan_version == 1 else 0)
        self.assertEqual(len([q for q in self.rows(Quest) if q["status"] == "active"]), 1)

    def test_busy_writer_returns_recoverable_storage_busy_without_mutation(self):
        line = self.create()
        other = create_sqlite_engine(self.url)
        self.addCleanup(other.dispose)
        @event.listens_for(other, "connect")
        def short_test_timeout(connection, _record):
            connection.execute("PRAGMA busy_timeout=20")
        before = self.snapshot()
        with unit_of_work(self.database, write=True):
            error = self.assert_error("STORAGE_BUSY", lambda: QuestService(other).complete_quest(line.current_quest.id, 1))
            self.assertTrue(error.retryable)
        self.assertEqual(before, self.snapshot())

    def test_pause_resume_preserves_pointer_and_xp_and_replays_safely(self):
        line = self.create()
        key = str(uuid4())
        paused = self.service.set_paused(line.id, 1, paused=True, idempotency_key=key)
        self.assertEqual((paused.status, paused.current_quest.status, paused.revision), ("paused", "paused", 2))
        self.assertEqual(paused.current_quest.id, line.current_quest.id)
        self.assert_error("QUESTLINE_PAUSED", lambda: self.service.complete_quest(line.current_quest.id, 2))
        no_op = self.service.set_paused(line.id, 1, paused=True, idempotency_key=str(uuid4()))
        self.assertEqual(no_op.revision, 2)
        resumed = self.service.set_paused(line.id, 2, paused=False, idempotency_key=str(uuid4()))
        self.assertEqual(resumed.revision, 3)
        replay = self.service.set_paused(line.id, 1, paused=True, idempotency_key=key)
        self.assertEqual((replay.status, replay.revision), ("active", 3))
        self.assert_error("IDEMPOTENCY_CONFLICT", lambda: self.service.set_paused(line.id, 3, paused=False, idempotency_key=key))
        self.assertEqual(self.service.get_profile().total_xp, 0)
        self.assertEqual(len(self.rows(Completion)), 0)

    def test_pause_stale_rejected_and_receipt_not_recorded(self):
        line = self.create()
        self.assert_error("STALE_REVISION", lambda: self.service.set_paused(line.id, 2, paused=True, idempotency_key=str(uuid4())))
        self.assertFalse(self.rows(TransitionReceipt))

    def test_replan_preserves_completed_snapshot_xp_and_audit(self):
        line = self.create()
        line = self.service.complete_quest(line.current_quest.id, 1).questline
        completed = [q for q in self.rows(Quest) if q["status"] == "completed"]
        awards = self.rows(Completion)
        original_unfinished = [q for q in self.rows(Quest) if q["status"] != "completed"]
        result = self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(2, "Replacement")),
                                                  context(), summary="New context", reason="Less time")
        self.assertEqual((result.revision, result.plan_version, result.current_quest.order), (3, 2, 2))
        self.assertEqual(result.progress.model_dump(), {"completed_count": 1, "remaining_count": 2, "total_count": 3})
        self.assertEqual(completed, [q for q in self.rows(Quest) if q["status"] == "completed"])
        self.assertEqual(awards, self.rows(Completion))
        self.assertEqual(self.service.get_profile().total_xp, 10)
        self.assertEqual(len(self.rows(PlanVersion)), 2)
        for old in original_unfinished:
            stored = next(q for q in self.rows(Quest) if q["id"] == old["id"])
            self.assertEqual(stored["status"], "superseded")
            self.assertIsNotNone(stored["superseded_at"])
            self.assert_error("QUEST_NOT_FOUND", lambda: self.service.complete_quest(old["id"], result.revision))
            for field in ("id", "title", "action", "hint"):
                self.assertNotIn(old[field], result.model_dump_json())
        while result.current_quest:
            result = self.service.complete_quest(result.current_quest.id, result.revision).questline
        self.assertEqual(result.status, "completed")
        self.assertEqual(len(result.completed_quests), 3)
        self.assertEqual(self.service.get_profile().total_xp, 40)

    def test_replan_single_quest_and_multiple_versions(self):
        line = self.create()
        for count in (1, 5, 2):
            line = self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(count, f"v{line.revision}")),
                                                  context(), summary="Revised fixture")
            self.assertEqual(line.progress.remaining_count, count)
            self.assertEqual(len([q for q in self.rows(Quest) if q["status"] == "active"]), 1)
        self.assertEqual(line.plan_version, 4)
        self.assertEqual(self.service.get_profile().total_xp, 0)

    def test_replan_rejects_stale_paused_completed_and_changed_goal(self):
        line = self.create()
        plan = ReplacementPlan(**proposal(1, "Replacement"))
        before = self.snapshot()
        self.assert_error("STALE_REVISION", lambda: self.service.replace_unfinished(line.id, 99, plan, context(), summary="Summary"))
        changed = context().model_copy(update={"goal": "Different goal"})
        self.assert_error("VALIDATION_ERROR", lambda: self.service.replace_unfinished(line.id, 1, plan, changed, summary="Summary"))
        self.assertEqual(before, self.snapshot())
        paused = self.service.set_paused(line.id, 1, paused=True, idempotency_key=str(uuid4()))
        before = self.snapshot()
        self.assert_error("QUESTLINE_PAUSED", lambda: self.service.replace_unfinished(line.id, paused.revision, plan, context(), summary="Summary"))
        self.assertEqual(before, self.snapshot())
        line = self.service.set_paused(line.id, paused.revision, paused=False, idempotency_key=str(uuid4()))
        while line.current_quest:
            line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        self.assert_error("INVALID_STATE", lambda: self.service.replace_unfinished(line.id, line.revision, plan, context(), summary="Summary"))

    def test_replan_rejects_repeat_of_completed_action(self):
        line = self.create()
        completed_action = line.current_quest.action
        line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        raw = proposal(1, "Replacement")
        raw["quests"][0]["action"] = "  " + completed_action.upper() + "  "
        before = self.snapshot()
        self.assert_error("VALIDATION_ERROR", lambda: self.service.replace_unfinished(line.id, line.revision,
                          ReplacementPlan(**raw), context(), summary="Summary"))
        self.assertEqual(before, self.snapshot())

    def test_mutated_proposals_revalidated_before_any_write(self):
        line = self.create()
        for field, value in (("estimated_minutes", 0), ("difficulty", "impossible"), ("action", " ")):
            plan = ReplacementPlan(**proposal(1, "Replacement"))
            setattr(plan.quests[0], field, value)
            before = self.snapshot()
            with self.assertRaises(ValidationError):
                self.service.replace_unfinished(line.id, 1, plan, context(), summary="Summary")
            self.assertEqual(before, self.snapshot())
        plan = QuestPlan(**proposal())
        plan.quests[0].estimated_minutes = 21
        before = self.snapshot()
        with self.assertRaises(ValidationError):
            self.service.create_questline(context(), plan, summary="Summary")
        self.assertEqual(before, self.snapshot())

    def fail_nth_write(self, operation, index):
        count = 0
        def fail(connection, cursor, statement, params, execution_context, executemany):
            nonlocal count
            if statement.lstrip().split()[0].upper() in ("INSERT", "UPDATE", "DELETE"):
                count += 1
                if count == index:
                    raise OperationalError(statement, params, sqlite3.OperationalError("simulated private failure"))
        before = self.snapshot()
        event.listen(self.database, "before_cursor_execute", fail)
        try:
            self.assert_error("STORAGE_UNAVAILABLE", operation)
        finally:
            event.remove(self.database, "before_cursor_execute", fail)
        self.assertEqual(before, self.snapshot())

    def test_completion_rollback_at_every_write_stage(self):
        line = self.create()
        for index in range(1, 6):
            with self.subTest(write=index):
                self.fail_nth_write(lambda: self.service.complete_quest(line.current_quest.id, 1), index)

    def test_replan_rollback_at_every_write_stage(self):
        line = self.create()
        line = self.service.complete_quest(line.current_quest.id, 1).questline
        for index in range(1, 6):
            with self.subTest(write=index):
                self.fail_nth_write(lambda: self.service.replace_unfinished(line.id, line.revision,
                                   ReplacementPlan(**proposal(2, "Replacement")), context(), summary="Summary"), index)

    def test_creation_and_pause_rollback(self):
        for index in range(1, 5):
            with self.subTest(create_write=index):
                self.fail_nth_write(self.create, index)
        line = self.create()
        for index in range(1, 4):
            with self.subTest(pause_write=index):
                self.fail_nth_write(lambda: self.service.set_paused(line.id, 1, paused=True, idempotency_key=str(uuid4())), index)

    def test_deferred_commit_failure_rolls_back_completion(self):
        line = self.create()
        from app.services.quests import verify_database as actual_verify
        def break_pointer(session):
            actual_verify(session)
            session.get(Questline, line.id).active_quest_id = str(uuid4())
        before = self.snapshot()
        with patch("app.services.quests.verify_database", side_effect=break_pointer):
            self.assert_error("STORAGE_UNAVAILABLE", lambda: self.service.complete_quest(line.current_quest.id, 1))
        self.assertEqual(before, self.snapshot())

    def test_foreign_keys_uniqueness_reward_and_integer_constraints(self):
        line = self.create()
        for sql in (
            "UPDATE questlines SET profile_id=999",
            "UPDATE quests SET status='active' WHERE status='locked'",
            "UPDATE quests SET xp_reward=20 WHERE difficulty='easy'",
            "UPDATE quests SET estimated_minutes=1.5",
            "UPDATE profiles SET total_xp=-1",
            "INSERT INTO profiles(id,total_xp,created_at,updated_at) VALUES(2,0,'x','x')",
            "UPDATE quests SET plan_version=99",
            "UPDATE quests SET status='completed' WHERE status='active'",
        ):
            before = self.snapshot()
            with self.subTest(sql=sql):
                def invalid():
                    with unit_of_work(self.database, write=True) as session:
                        session.execute(text(sql))
                self.assert_error("STORAGE_UNAVAILABLE", invalid)
                self.assertEqual(before, self.snapshot())
        second = self.create()
        def cross_pointer():
            with unit_of_work(self.database, write=True) as session:
                session.get(Questline, line.id).active_quest_id = second.current_quest.id
        self.assert_error("STORAGE_UNAVAILABLE", cross_pointer)

    def test_ledger_unique_quest_and_matching_reward_foreign_key(self):
        line = self.create()
        self.service.complete_quest(line.current_quest.id, 1)
        for quest_id, award in ((line.current_quest.id, 10), (str(uuid4()), 10)):
            def insert():
                with unit_of_work(self.database, write=True) as session:
                    session.add(Completion(quest_id=quest_id, profile_id=1, xp_awarded=award, completed_at=utc_text()))
            self.assert_error("STORAGE_UNAVAILABLE", insert)
        active = self.service.get_questline(line.id).current_quest
        def wrong_award():
            with unit_of_work(self.database, write=True) as session:
                session.add(Completion(quest_id=active.id, profile_id=1, xp_awarded=10, completed_at=utc_text()))
        self.assert_error("STORAGE_UNAVAILABLE", wrong_award)

    def test_unknown_schema_version_and_missing_index_are_not_reset(self):
        for mode in ("unknown", "version", "index"):
            path = Path(self.directory.name) / f"{mode}.db"
            engine = create_sqlite_engine(f"sqlite:///{path}")
            self.addCleanup(engine.dispose)
            if mode != "unknown":
                initialize_database(engine)
            with unit_of_work(engine, write=True) as session:
                session.execute(text({"unknown": "CREATE TABLE unrelated (id INTEGER PRIMARY KEY)",
                                      "version": "PRAGMA user_version=99", "index": "DROP INDEX uq_quest_current"}[mode]))
            with engine.connect() as connection:
                before = connection.execute(text("SELECT type,name,sql FROM sqlite_master ORDER BY name")).all()
            self.assert_error("STORAGE_UNAVAILABLE", lambda: initialize_database(engine))
            with engine.connect() as connection:
                self.assertEqual(before, connection.execute(text("SELECT type,name,sql FROM sqlite_master ORDER BY name")).all())

    def test_bootstrap_refuses_corrupt_state_without_repair(self):
        line = self.create()
        with unit_of_work(self.database, write=True) as session:
            session.get(Profile, 1).total_xp = 100
        before = self.snapshot()
        self.assert_error("STORAGE_UNAVAILABLE", lambda: initialize_database(self.database))
        self.assertEqual(before, self.snapshot())
        with unit_of_work(self.database, write=True) as session:
            session.get(Profile, 1).total_xp = 0
            session.get(Quest, line.current_quest.id).status = "locked"
        self.assert_error("STORAGE_UNAVAILABLE", lambda: initialize_database(self.database))

    def test_saved_list_pagination_status_and_empty_result(self):
        self.assertFalse(self.service.list_questlines().items)
        first, second = self.create(), self.create()
        page = self.service.list_questlines(limit=1)
        self.assertTrue(page.has_more)
        self.assertEqual(page.items[0].id, second.id)
        self.assertEqual(self.service.list_questlines(limit=1, offset=1).items[0].id, first.id)
        paused = self.service.set_paused(first.id, 1, paused=True, idempotency_key=str(uuid4()))
        self.assertEqual([v.id for v in self.service.list_questlines(status="paused").items], [paused.id])
        for options in ({"limit": 0}, {"offset": -1}, {"limit": True}, {"status": "superseded"}):
            self.assert_error("VALIDATION_ERROR", lambda: self.service.list_questlines(**options))

    def test_file_reopening_and_new_process_preserve_progress_and_receipts(self):
        line = self.create()
        line = self.service.complete_quest(line.current_quest.id, 1).questline
        line = self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(1, "Replacement")),
                                               context(), summary="New fixture")
        key, revision = str(uuid4()), line.revision
        line = self.service.set_paused(line.id, revision, paused=True, idempotency_key=key)
        expected = {"profile": self.service.get_profile().model_dump(), "line": line.model_dump(mode="json")}
        self.database.dispose()
        reopened = create_sqlite_engine(self.url)
        self.addCleanup(reopened.dispose)
        initialize_database(reopened)
        self.assertEqual(QuestService(reopened).get_questline(line.id).model_dump(mode="json"), expected["line"])
        code = """import json,sys
from app.database import create_sqlite_engine
from app.schema import initialize_database
from app.services.quests import QuestService
engine=create_sqlite_engine(sys.argv[1]); initialize_database(engine); service=QuestService(engine)
print(json.dumps({'profile':service.get_profile().model_dump(),'line':service.set_paused(sys.argv[2],int(sys.argv[3]),paused=True,idempotency_key=sys.argv[4]).model_dump(mode='json')}))
engine.dispose()
"""
        result = subprocess.run([sys.executable, "-c", code, self.url, line.id, str(revision), key], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)


class QuestAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.database = create_sqlite_engine(f"sqlite:///{Path(self.directory.name) / 'api.db'}")
        self.engine_patch = patch("app.main.engine", self.database)
        self.engine_patch.start()
        self.lifespan = app.router.lifespan_context(app)
        await self.lifespan.__aenter__()
        self.service = app.state.quests
        self.line = self.service.create_questline(context(), QuestPlan(**proposal()), summary="Fictional summary")
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.engine_patch.stop()
        self.directory.cleanup()

    async def test_read_complete_pause_resume_contracts_without_ollama(self):
        with patch.object(app.state.ollama, "generate", side_effect=AssertionError("AI must not be used")), \
             patch.object(app.state.ollama, "generate_quest_plan", side_effect=AssertionError("AI must not be used")):
            for path in ("/api/health", "/api/profile", "/api/questlines", f"/api/questlines/{self.line.id}"):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.headers["cache-control"], "no-store")
            response = await self.client.post(f"/api/questlines/{self.line.id}/pause", json={"expected_revision": 1},
                                              headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["current_quest"]["status"], "paused")
            response = await self.client.post(f"/api/questlines/{self.line.id}/resume", json={"expected_revision": 2},
                                              headers={"Idempotency-Key": str(uuid4())})
            self.assertEqual(response.status_code, 200, response.text)
            response = await self.client.post(f"/api/quests/{self.line.current_quest.id}/complete", json={"expected_revision": 3})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["profile"], {"id": 1, "total_xp": 10, "level": 1})
            response = await self.client.post(f"/api/quests/{self.line.current_quest.id}/complete", json={"expected_revision": 1})
            self.assertEqual(response.json()["awarded_xp"], 0)

    async def test_visibility_errors_and_validation_are_safe(self):
        with unit_of_work(self.database) as session:
            hidden = session.scalar(select(Quest).where(Quest.status == "locked"))
            hidden_id, hidden_action = hidden.id, hidden.action
        for body in ({"expected_revision": True}, {"expected_revision": "1"}, {"expected_revision": 0},
                     {"expected_revision": 1, "private_goal": "PRIVATE_SENTINEL"}):
            response = await self.client.post(f"/api/quests/{self.line.current_quest.id}/complete", json=body)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["error"]["code"], "VALIDATION_ERROR")
            self.assertNotIn("PRIVATE_SENTINEL", response.text)
            self.assertNotIn("input", response.text)
        hidden_response = await self.client.post(f"/api/quests/{hidden_id}/complete", json={"expected_revision": 1})
        unknown_response = await self.client.post(f"/api/quests/{uuid4()}/complete", json={"expected_revision": 1})
        self.assertEqual(hidden_response.status_code, 404)
        self.assertEqual(hidden_response.json()["error"]["code"], unknown_response.json()["error"]["code"])
        for path in ("/api/questlines", f"/api/questlines/{self.line.id}"):
            response = await self.client.get(path)
            self.assertNotIn(hidden_action, response.text)
            self.assertNotIn(hidden_id, response.text)
        for path in ("/api/questlines/not-a-uuid", "/api/questlines?limit=0", "/api/questlines?status=locked"):
            self.assertEqual((await self.client.get(path)).status_code, 422)

    async def test_idempotency_header_and_cors(self):
        path = f"/api/questlines/{self.line.id}/pause"
        for headers in ({}, {"Idempotency-Key": "bad"}):
            self.assertEqual((await self.client.post(path, json={"expected_revision": 1}, headers=headers)).status_code, 422)
        response = await self.client.options(path, headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
                                                           "Access-Control-Request-Headers": "content-type,idempotency-key"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Idempotency-Key", response.headers["access-control-allow-headers"])

    async def test_storage_and_unexpected_errors_are_sanitized(self):
        app.state.database_available = False
        response = await self.client.get("/api/profile")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "STORAGE_UNAVAILABLE")
        health = await self.client.get("/api/health")
        self.assertEqual(health.status_code, 503)
        self.assertFalse(health.json()["components"]["database"]["available"])
        app.state.database_available = True
        with patch.object(self.service, "get_profile", side_effect=ValueError("PRIVATE_SENTINEL SQL statement")):
            response = await self.client.get("/api/profile")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("PRIVATE_SENTINEL", response.text)
        self.assertEqual(response.headers["cache-control"], "no-store")

    async def test_no_generation_or_replan_product_endpoints(self):
        self.assertEqual((await self.client.post("/api/questlines", json={})).status_code, 405)
        self.assertEqual((await self.client.post(f"/api/questlines/{self.line.id}/replan", json={})).status_code, 404)
        self.assertEqual((await self.client.post("/api/check-in", json={})).status_code, 404)


class StorageStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_database_keeps_diagnostics_available(self):
        with tempfile.TemporaryDirectory() as directory:
            database = create_sqlite_engine(f"sqlite:///{Path(directory) / 'unknown.db'}")
            with unit_of_work(database, write=True) as session:
                session.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)"))
            with patch("app.main.engine", database):
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://api.test") as client:
                        self.assertEqual((await client.get("/api/health")).status_code, 503)
                        self.assertEqual((await client.get("/api/profile")).status_code, 503)
            with database.connect() as connection:
                self.assertEqual(connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all(), ["unrelated"])
            database.dispose()
