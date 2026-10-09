import json
import sqlite3
import unittest
from unittest.mock import patch

import httpx
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError

from app.encouragement import TAILS, completed_encouragement
from app.errors import QuestError
from app.models import Quest
from app.schema import CATALOG_SQL, SCHEMA_VERSION, expected_catalog, initialize_database, normalize_catalog
from app.schemas import QuestPlan, ReplacementPlan
from app.database import unit_of_work
import test_quests as engine_tests
import test_structured_ai as ai_tests
from test_quests import proposal, context
from test_structured_ai import valid_plan, outer


def with_messages(count=3):
    raw = proposal(count)
    for index, quest in enumerate(raw["quests"]):
        quest["completion_encouragement"] = f'You completed "{quest["title"]}". {TAILS[index % len(TAILS)]}'
    return raw


class EncouragementSchemaTests(unittest.TestCase):
    def test_optional_invalid_copy_never_rejects_valid_plan(self):
        for message in (None, "", "Well done!", 123, {}, [], "x" * 501,
                        'You mastered Python! Stage 2 is all about SECRET_FUTURE.',
                        'You completed "Initial quest 0". Your entire goal is finished.'):
            with self.subTest(message_type=type(message).__name__):
                raw = proposal()
                raw["quests"][0]["completion_encouragement"] = message
                plan = QuestPlan.model_validate_json(json.dumps(raw))
                self.assertIsNone(plan.quests[0].completion_encouragement)

    def test_copy_is_grounded_and_bounded_without_factual_achievement_claims(self):
        plan = QuestPlan(**with_messages())
        messages = [quest.completion_encouragement for quest in plan.quests]
        self.assertEqual(len(set(messages)), 3)
        for quest in plan.quests:
            self.assertIn(quest.title, quest.completion_encouragement)
            self.assertLessEqual(len(quest.completion_encouragement.split()), 35)
        raw = with_messages()
        raw["quests"][0]["completion_encouragement"] = raw["quests"][1]["completion_encouragement"]
        self.assertIsNone(QuestPlan(**raw).quests[0].completion_encouragement)
        self.assertLessEqual(len(completed_encouragement(" ".join(["word"] * 50), None).split()), 35)
        bounded = completed_encouragement("Title", None, action="x" * 2000)
        self.assertLessEqual(len(bounded), 500)
        self.assertLessEqual(len(bounded.split()), 35)


class EncouragementEngineTests(unittest.TestCase):
    setUp = engine_tests.QuestEngineTests.setUp
    snapshot = engine_tests.QuestEngineTests.snapshot
    rows = engine_tests.QuestEngineTests.rows

    def test_reveal_only_after_completion_and_duplicate_is_stable(self):
        raw = with_messages()
        line = self.service.create_questline(context(), QuestPlan(**raw), summary="Fictional data")
        before = self.service.get_questline(line.id)
        self.assertIsNone(before.current_quest.completion_encouragement)
        for quest in raw["quests"]:
            self.assertNotIn(quest["completion_encouragement"], before.model_dump_json())
        result = self.service.complete_quest(line.current_quest.id, line.revision)
        self.assertEqual(result.awarded_xp, 10)
        completed = result.questline.completed_quests[0]
        self.assertEqual(completed.completion_encouragement, completed_encouragement(completed.title, raw["quests"][0]["completion_encouragement"], action=completed.action))
        self.assertIn(completed.action, completed.completion_encouragement)
        self.assertTrue(completed.completion_encouragement.endswith(TAILS[0]))
        self.assertIsNone(result.questline.current_quest.completion_encouragement)
        snapshot = self.snapshot()
        replay = self.service.complete_quest(completed.id, line.revision)
        self.assertEqual(replay.awarded_xp, 0)
        self.assertEqual(replay.questline.completed_quests[0].completion_encouragement, completed.completion_encouragement)
        self.assertEqual(self.snapshot(), snapshot)

    def test_missing_message_final_completion_and_restart_use_specific_fallback(self):
        line = self.service.create_questline(context(), QuestPlan(**proposal()), summary="Legacy-style absent messages")
        messages = []
        with patch("app.ollama.OllamaClient.generate_quest_plan", side_effect=AssertionError("Completion must not call AI")):
            while line.current_quest:
                title = line.current_quest.title
                result = self.service.complete_quest(line.current_quest.id, line.revision)
                line = result.questline
                message = line.completed_quests[-1].completion_encouragement
                self.assertIn(title, message)
                messages.append(message)
        self.assertEqual(len(set(messages)), 3)
        self.assertEqual(line.status, "completed")
        self.assertEqual(self.service.get_profile().total_xp, 60)
        self.database.dispose()
        initialize_database(self.database)
        self.assertEqual(self.service.get_questline(line.id).model_dump(), line.model_dump())

    def test_replan_keeps_completed_message_and_hides_superseded_copy(self):
        line = self.service.create_questline(context(), QuestPlan(**with_messages()), summary="Fictional plan")
        line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        completed = line.completed_quests[0].model_dump()
        hidden = with_messages()["quests"][1]["completion_encouragement"]
        replacement = ReplacementPlan(**proposal(2, prefix="Replacement"))
        line = self.service.replace_unfinished(line.id, line.revision, replacement, context(), summary="Changed pace")
        self.assertEqual(line.completed_quests[0].model_dump(), completed)
        self.assertNotIn(hidden, line.model_dump_json())
        self.assertEqual(self.service.get_profile().total_xp, 10)

    def legacy_v3(self):
        line = self.service.create_questline(context(), QuestPlan(**proposal()), summary="Existing v3 campaign")
        line = self.service.complete_quest(line.current_quest.id, line.revision).questline
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("ALTER TABLE quests DROP COLUMN completion_encouragement"))
            session.execute(text("PRAGMA user_version=3"))
            self.assertEqual(normalize_catalog(session.connection().exec_driver_sql(CATALOG_SQL)), expected_catalog(3))
        return line

    def legacy_rows(self):
        with unit_of_work(self.database) as session:
            result = {}
            for kind, name, _ in expected_catalog(3):
                if kind == "table":
                    columns = [row[1] for row in session.execute(text(f"PRAGMA table_info({name})")) if row[1] != "completion_encouragement"]
                    result[name] = session.execute(text(f"SELECT {', '.join(columns)} FROM {name} ORDER BY 1,2")).all()
            return result

    def test_v3_v4_migration_preserves_every_original_row_and_restarts(self):
        line = self.legacy_v3()
        before = self.legacy_rows()
        initialize_database(self.database)
        self.assertEqual(self.legacy_rows(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), SCHEMA_VERSION)
            self.assertEqual(session.scalar(text("PRAGMA foreign_keys")), 1)
            self.assertEqual(session.execute(text("PRAGMA foreign_key_check")).all(), [])
            self.assertTrue(all(q.completion_encouragement is None for q in session.scalars(select(Quest))))
        self.assertEqual(self.service.get_questline(line.id).model_dump(), line.model_dump())
        initialize_database(self.database)
        self.assertEqual(self.legacy_rows(), before)
        self.assertEqual(self.service.complete_quest(line.current_quest.id, line.revision).awarded_xp, 20)

    def test_failed_v3_v4_migration_rolls_back_column_version_and_data(self):
        self.legacy_v3()
        before = self.legacy_rows()
        def fail(connection, cursor, statement, params, execution_context, executemany):
            if statement == "PRAGMA user_version=4":
                raise OperationalError(statement, params, sqlite3.OperationalError("injected migration failure"))
        event.listen(self.database, "before_cursor_execute", fail)
        try:
            with self.assertRaises(QuestError):
                initialize_database(self.database)
        finally:
            event.remove(self.database, "before_cursor_execute", fail)
        self.assertEqual(self.legacy_rows(), before)
        with unit_of_work(self.database) as session:
            self.assertEqual(session.scalar(text("PRAGMA user_version")), 3)
            self.assertEqual(normalize_catalog(session.connection().exec_driver_sql(CATALOG_SQL)), expected_catalog(3))
        initialize_database(self.database)

    def test_mismatched_v3_schema_is_preserved_and_refused(self):
        self.legacy_v3()
        with unit_of_work(self.database, write=True) as session:
            session.execute(text("DROP INDEX uq_quest_current"))
        before = self.legacy_rows()
        with self.assertRaises(QuestError):
            initialize_database(self.database)
        self.assertEqual(self.legacy_rows(), before)


class OptionalCopyGenerationTests(unittest.IsolatedAsyncioTestCase):
    generate = ai_tests.StructuredGenerationTests.generate

    async def test_invalid_optional_copy_needs_no_retry_or_extra_call(self):
        raw = valid_plan()
        raw["quests"][0]["completion_encouragement"] = {"invalid": "SECRET_FUTURE"}
        result = await self.generate([outer(raw)])
        self.assertEqual(len(self.requests), 1)
        self.assertIsNone(result.plan.quests[0].completion_encouragement)
        self.assertTrue(result.attempts[0].validation_success)
        self.assertIn("completion_encouragement", json.loads(self.requests[0].content)["system"])
