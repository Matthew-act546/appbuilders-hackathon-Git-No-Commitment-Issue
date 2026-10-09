"""Adaptive count bounds, whole-goal capacity, persistence and v2 migration."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError

from app.database import create_sqlite_engine, unit_of_work
from app.errors import QuestError
from app.models import Profile, Quest, Questline
from app.schema import expected_catalog, initialize_database, normalize_catalog, CATALOG_SQL, SCHEMA_VERSION
from app.schemas import CheckInStart, QuestPlan, ReplacementPlan, QuestlineContext, ReplanRequest, PlanMetadata
from app.services.check_in import CheckInService
from app.services.quests import QuestService, utc_text, add_version, verify_database
from test_quests import proposal, context
import test_check_in as helpers


class AdaptiveSchemaTests(unittest.TestCase):
    def test_all_initial_counts_two_through_six_and_legacy_counts(self):
        for count in (2, 3, 4, 5, 6):
            with self.subTest(count=count):
                self.assertEqual(len(QuestPlan(**proposal(count)).quests), count)
        for count in (0, 1, 7):
            with self.subTest(count=count), self.assertRaises(ValidationError):
                QuestPlan(**proposal(count))
        for count in (1, 2, 6):
            self.assertEqual(len(ReplacementPlan(**proposal(count)).quests), count)

    def test_campaign_can_span_sessions_but_first_action_must_fit(self):
        raw = proposal(6)
        for quest in raw["quests"][1:]:
            quest["estimated_minutes"] = 90
        plan = QuestPlan.model_validate(raw, context={"available_minutes": 5})
        self.assertGreater(sum(q.estimated_minutes for q in plan.quests), 5)
        raw["quests"][0]["estimated_minutes"] = 6
        with self.assertRaises(ValidationError):
            QuestPlan.model_validate(raw, context={"available_minutes": 5})

    def test_remaining_slot_limit_does_not_force_filler(self):
        self.assertEqual(len(ReplacementPlan.model_validate(proposal(1), context={"available_minutes": 5, "max_quests": 1}).quests), 1)
        with self.assertRaises(ValidationError):
            ReplacementPlan.model_validate(proposal(2), context={"available_minutes": 5, "max_quests": 1})


class AdaptiveEngineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.url = f"sqlite:///{Path(self.directory.name) / 'state.db'}"
        self.database = create_sqlite_engine(self.url)
        self.addCleanup(self.database.dispose)
        initialize_database(self.database)
        self.service = QuestService(self.database)

    def create(self, count):
        return self.service.create_questline(context(), QuestPlan(**proposal(count)), summary="Fictional complete goal")

    def test_two_three_and_six_stage_unlocking_xp_and_visibility(self):
        expected_profile = 0
        for count in (2, 3, 6):
            line = self.create(count)
            self.assertEqual(line.progress.total_count, count)
            with unit_of_work(self.database) as session:
                rows = list(session.scalars(select(Quest).where(Quest.questline_id == line.id)))
                self.assertEqual(sum(q.status == "active" for q in rows), 1)
                public = json.dumps(line.model_dump(mode="json"))
                for hidden in (q for q in rows if q.status == "locked"):
                    for value in (hidden.id, hidden.title, hidden.action, hidden.completion_criteria, hidden.hint):
                        self.assertNotIn(value, public)
            campaign_xp = 0
            for stage in range(count):
                current = line.current_quest
                reward = current.xp_reward
                result = self.service.complete_quest(current.id, line.revision)
                campaign_xp += reward
                expected_profile += reward
                self.assertEqual(result.profile.total_xp, expected_profile)
                line = result.questline
                duplicate = self.service.complete_quest(current.id, 1)
                self.assertEqual(duplicate.awarded_xp, 0)
                self.assertEqual(duplicate.profile.total_xp, expected_profile)
                self.assertEqual(line.progress.completed_count, stage + 1)
                self.assertEqual(line.current_quest.order if line.current_quest else count + 1, stage + 2)
            self.assertEqual(line.status, "completed")
            self.assertEqual(sum(q.xp_reward for q in line.completed_quests), campaign_xp)

    def test_six_stage_reopening_restores_current_progress_and_xp(self):
        line = self.create(6)
        line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        before = line.model_dump()
        self.database.dispose()
        reopened = create_sqlite_engine(self.url)
        try:
            initialize_database(reopened)
            service = QuestService(reopened)
            self.assertEqual(service.get_questline(line.id).model_dump(), before)
            self.assertEqual(service.get_profile().total_xp, 10)
        finally:
            reopened.dispose()

    def test_replan_without_history_cannot_shrink_total_below_two(self):
        line = self.create(2)
        before = line.model_dump()
        with self.assertRaises(QuestError) as error:
            self.service.replace_unfinished(line.id, 1, ReplacementPlan(**proposal(1, prefix="Remaining")), context(), summary="Too few")
        self.assertEqual(error.exception.code, "VALIDATION_ERROR")
        self.assertEqual(self.service.get_questline(line.id).model_dump(), before)
        line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        updated = self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(1, prefix="Remaining")), context(), summary="One remaining")
        self.assertEqual(updated.progress.total_count, 2)
        self.assertEqual(self.service.get_profile().total_xp, 10)

    def test_replan_preserves_completed_history_and_rejects_over_six_atomically(self):
        line = self.create(6)
        for _ in range(2):
            line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        history = [q.model_dump() for q in line.completed_quests]
        before = line.model_dump()
        with self.assertRaises(QuestError) as result:
            self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(5, prefix="Replacement")), context(), summary="Changed pace")
        self.assertEqual(result.exception.code, "VALIDATION_ERROR")
        self.assertEqual(self.service.get_questline(line.id).model_dump(), before)
        replaced = self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(4, prefix="Replacement")), context(), summary="Changed pace")
        self.assertEqual([q.model_dump() for q in replaced.completed_quests], history)
        self.assertEqual(replaced.progress.total_count, 6)
        self.assertEqual(self.service.get_profile().total_xp, 30)
        with unit_of_work(self.database) as session:
            self.assertEqual(len(list(session.scalars(select(Quest).where(Quest.questline_id == line.id, Quest.status == "superseded")))), 4)
        with self.assertRaises(QuestError) as stale:
            self.service.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(1, prefix="Stale")), context(), summary="Stale")
        self.assertEqual(stale.exception.code, "STALE_REVISION")


class AdaptivePipelineTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = helpers.PipelineTests.asyncSetUp
    asyncTearDown = helpers.PipelineTests.asyncTearDown
    adapter = helpers.PipelineTests.adapter
    request = helpers.PipelineTests.request

    async def test_simple_two_and_complex_six_are_model_selected_not_padded(self):
        for count, goal in ((2, "Organize my desk using existing storage"), (6, "Create a complete local field guide with notes, diagrams, examples and review questions")):
            first, _ = self.service.submit(CheckInStart(mode="start", goal=goal, available_minutes=5, energy="low"), str(uuid4()))
            raw = proposal(count)
            for quest in raw["quests"][1:]:
                quest["estimated_minutes"] = 30
            result = await self.service.generate(self.request(first), str(uuid4()), self.adapter([raw]))
            self.assertEqual(result.view.progress.total_count, count)
            payload = self.calls[-1]
            self.assertEqual(payload["format"]["properties"]["quests"]["minItems"], 2)
            self.assertEqual(payload["format"]["properties"]["quests"]["maxItems"], 6)
            self.assertIn("smallest number of meaningful stages", payload["system"])
            self.assertIn("Do not assume the whole goal must be completed within the current session", payload["system"])
            self.assertEqual(len(result.generation.attempts), 1)
        self.assertEqual(len(self.calls), 2)  # No complexity classification/review.

    async def test_last_remaining_replan_slot_is_one_and_history_xp_survive(self):
        line = self.quests.create_questline(context(), QuestPlan(**proposal(6)), summary="Fictional whole goal")
        for _ in range(5):
            line = self.quests.complete_quest(line.current_quest.id, line.revision).questline
        before = [q.model_dump() for q in line.completed_quests]
        result = await self.service.generate(ReplanRequest(expected_revision=line.revision, available_minutes=5, energy="low"), str(uuid4()), self.adapter([proposal(1, prefix="Remaining")]), line_id=line.id)
        self.assertEqual(self.calls[-1]["format"]["properties"]["quests"]["maxItems"], 1)
        self.assertEqual(result.view.progress.total_count, 6)
        self.assertEqual([q.model_dump() for q in result.view.completed_quests], before)
        self.assertEqual(self.quests.get_profile().total_xp, 90)


class CountMigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = create_sqlite_engine(f"sqlite:///{Path(self.directory.name) / 'legacy.db'}")
        self.addCleanup(self.database.dispose)
        with unit_of_work(self.database, write=True) as session:
            for kind, name, sql in sorted(expected_catalog(2), key=lambda row: (row[0] != "table", row[1])):
                session.connection().exec_driver_sql(sql)
            now = utc_text()
            session.add(Profile(id=1, total_xp=0, created_at=now, updated_at=now))
            session.connection().exec_driver_sql("PRAGMA user_version=2")
            session.connection().exec_driver_sql("ALTER TABLE quests ADD COLUMN completion_encouragement VARCHAR")
        self.quests = QuestService(self.database)
        for count in (3, 4, 5):
            line = self.quests.create_questline(context(), QuestPlan(**proposal(count)), summary="Legacy saved data")
            line = self.quests.complete_quest(line.current_quest.id, 1).questline
            self.quests.set_paused(line.id, line.revision, paused=True, idempotency_key=str(uuid4()))
        CheckInService(self.quests).submit(CheckInStart(mode="start", goal="Organize local materials", available_minutes=5, energy="low"), str(uuid4()))
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE quests DROP COLUMN completion_encouragement"))

    def snapshot(self):
        with unit_of_work(self.database) as session:
            return {name: session.execute(text(f"SELECT {', '.join(row[1] for row in session.execute(text(f'PRAGMA table_info({name})')) if row[1] != 'completion_encouragement')} FROM {name} ORDER BY 1,2")).all()
                    for kind, name, _ in expected_catalog(2) if kind == "table"}

    def test_v2_upgrade_preserves_all_rows_xp_history_receipts_and_foreign_keys(self):
        before = self.snapshot()
        initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.quests.get_profile().total_xp, 30)
        initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), SCHEMA_VERSION)
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)
            self.assertEqual(session.execute(text("PRAGMA foreign_key_check")).all(), [])
        for count in (2, 6):
            self.assertEqual(self.quests.create_questline(context(), QuestPlan(**proposal(count)), summary="New supported count").progress.total_count, count)

    def test_failure_after_old_table_drop_rolls_back_schema_rows_and_restores_fks(self):
        before = self.snapshot()
        def fail(connection, cursor, statement, params, execution_context, executemany):
            if statement.startswith("ALTER TABLE plan_versions_v3"):
                raise OperationalError(statement, params, sqlite3.OperationalError("injected rebuild failure"))
        event.listen(self.database, "before_cursor_execute", fail)
        try:
            with self.assertRaises(QuestError):
                initialize_database(self.database)
        finally:
            event.remove(self.database, "before_cursor_execute", fail)
        self.assertEqual(self.snapshot(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), 2)
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)
            self.assertEqual(normalize_catalog(session.connection().exec_driver_sql(CATALOG_SQL)), expected_catalog(2))
        initialize_database(self.database)

    def test_mismatched_v2_is_refused_without_reset(self):
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE plan_versions ADD COLUMN unexpected TEXT"))
        before = self.snapshot()
        with self.assertRaises(QuestError):
            initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), 2)
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)

    def test_legacy_history_over_six_is_preserved_and_completable_not_replanned(self):
        # Build a legitimate old-policy snapshot: four completed + five new
        # unfinished quests. New service intentionally cannot create this shape.
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE quests ADD COLUMN completion_encouragement VARCHAR"))
        line = self.quests.create_questline(context(), QuestPlan(**proposal(5)), summary="Legacy larger history")
        for _ in range(4):
            line = self.quests.complete_quest(line.current_quest.id, line.revision).questline
        with unit_of_work(self.database, write=True) as session:
            stored = session.get(Questline, line.id)
            old = session.get(Quest, stored.active_quest_id)
            now = utc_text()
            old.status, old.superseded_at, old.updated_at = "superseded", now, now
            session.flush()
            stored.plan_version, stored.revision, stored.updated_at = 2, stored.revision + 1, now
            stored.active_quest_id = add_version(session, stored, ReplacementPlan(**proposal(5, prefix="Legacy replacement")), PlanMetadata(summary="Old-policy snapshot"), now, initial=False, completed_count=4)
            session.flush()
            verify_database(session)
        line = self.quests.get_questline(line.id)
        for _ in range(2):
            line = self.quests.complete_quest(line.current_quest.id, line.revision).questline
        before, xp = self.snapshot(), self.quests.get_profile().total_xp
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE quests DROP COLUMN completion_encouragement"))
        initialize_database(self.database)
        self.assertEqual(self.snapshot(), before)
        with self.assertRaises(QuestError) as error:
            self.quests.replace_unfinished(line.id, line.revision, ReplacementPlan(**proposal(1, prefix="New")), context(), summary="Must preserve history")
        self.assertEqual(error.exception.code, "INVALID_STATE")
        body = ReplanRequest(expected_revision=line.revision, available_minutes=5, energy="low")
        with self.assertRaises(QuestError) as reserved:
            CheckInService(self.quests).reserve("replan", line.id, body, str(uuid4()))
        self.assertEqual(reserved.exception.code, "INVALID_STATE")
        self.assertEqual(self.quests.get_profile().total_xp, xp)
        while line.current_quest:
            line = self.quests.complete_quest(line.current_quest.id, line.revision).questline
        self.assertEqual(line.progress.completed_count, 9)
        self.assertEqual(line.status, "completed")
