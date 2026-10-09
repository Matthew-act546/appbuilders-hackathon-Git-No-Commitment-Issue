"""Phase 3D: subjective diagnostics cannot veto essential-valid proposals."""
import unittest
from unittest.mock import patch
from uuid import uuid4

from app.models import Questline
from app.ollama import OllamaClient
from app.quality import essential_checks
from app.schemas import GroundingContext, QuestPlan, QuestlineContext
import test_check_in as helpers
from test_check_in import plan_data


class EssentialPolicyTests(unittest.TestCase):
    def assess(self, raw, goal=helpers.SPECIFIC, minutes=20, energy="low", completed=None):
        context = QuestlineContext(goal=goal, available_minutes=minutes, energy=energy)
        return essential_checks(QuestPlan(**raw), context, GroundingContext(summary=goal, completed=completed or []))

    def test_subjective_action_criteria_and_low_energy_guidance_only_warn(self):
        raw = plan_data()
        raw["quests"][0].update(action="Work on it.", completion_criteria="Feel confident.", estimated_minutes=15, difficulty="hard")
        codes, warnings = self.assess(raw)
        self.assertEqual(codes, ())
        self.assertEqual(set(warnings), {"vague_action", "unobservable_criteria", "implausible_estimate", "inappropriate_difficulty"})

    def test_minor_sequence_and_duplicate_criteria_only_warn(self):
        raw = helpers.plan_data()
        raw["quests"][0].update(action="Research the endpoint in existing local notes.", completion_criteria="The slide contains a summary.")
        raw["quests"][2]["completion_criteria"] = raw["quests"][1]["completion_criteria"]
        codes, warnings = self.assess(raw)
        self.assertEqual(codes, ())
        self.assertIn("sequencing_imperfection", warnings)
        self.assertIn("unobservable_criteria", warnings)

    def test_optional_suggestion_warns_but_required_dependency_and_prohibition_block(self):
        raw = plan_data()
        raw["quests"][2]["action"] += " Optionally download a reporting tool."
        self.assertEqual(self.assess(raw)[0], ())
        self.assertIn("optional_tool_suggestion", self.assess(raw)[1])
        self.assertIn("explicit_constraint_violated", self.assess(raw, goal=helpers.SPECIFIC + "; no downloads")[0])
        raw["quests"][2]["action"] += " A cloud account is required; sign up before running the tests."
        self.assertIn("external_dependency", self.assess(raw)[0])

    def test_schema_capacity_and_missing_explicit_count_remain_hard(self):
        raw = plan_data(); raw["quests"][0]["estimated_minutes"] = 21
        self.assertIn("implausible_estimate", self.assess(raw)[0])
        raw = plan_data(); raw["quests"][1].update(action="Write two unit tests for the endpoint.", completion_criteria="Two tests are written.")
        self.assertIn("duplicate_or_contradiction", self.assess(raw)[0])

    def test_completed_work_repetition_cannot_become_a_warning(self):
        from app.schemas import CompletedMilestone
        raw = plan_data()
        completed = [CompletedMilestone(**{key: raw["quests"][0][key] for key in ("title", "action", "completion_criteria")})]
        self.assertIn("duplicate_or_contradiction", self.assess(raw, completed=completed)[0])


class EssentialPipelineTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = helpers.PipelineTests.asyncSetUp
    asyncTearDown = helpers.PipelineTests.asyncTearDown
    adapter = helpers.PipelineTests.adapter
    request = helpers.PipelineTests.request
    count = helpers.PipelineTests.count
    assert_error = helpers.PipelineTests.assert_error

    async def test_warnings_are_internal_and_save_once_without_review_or_xp(self):
        raw = plan_data(); raw["quests"][0]["completion_criteria"] = "Feel confident and ready."
        body, key = self.request(), str(uuid4())
        with patch.object(OllamaClient, "review_quest_plan", side_effect=AssertionError("No reviewer allowed")):
            result = await self.service.generate(body, key, self.adapter([raw]))
            replay = await self.service.generate(body, key, self.adapter([]))
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.view.id, result.view.id)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
        self.assertIn("unobservable_criteria", result.generation.assessments[0].warnings)
        public = result.view.model_dump()
        self.assertNotIn("warnings", public)
        self.assertNotIn(raw["quests"][1]["action"], str(public))

    async def test_essential_failure_gets_exactly_one_correction_without_review(self):
        raw = plan_data(); raw["quests"][0]["action"] = "Sign up for a required cloud service."
        body = self.request()
        result = await self.service.generate(body, str(uuid4()), self.adapter([raw, plan_data()]))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(result.generation.attempts), 2)
        self.assertIn("external_dependency", result.generation.attempts[0].semantic_codes)
        self.assertIsNone(result.review)
        self.assertEqual(self.count(Questline), 1)
