"""Deterministic regressions for the everyday-goal and shared-correction hotfix."""
from uuid import uuid4
import unittest

from app.models import Questline
from app.quality import clarification_question, deterministic_issues
from app.schemas import GroundingContext, QuestlineContext, QuestPlan
import test_check_in as helpers
from test_check_in import approval, plan_data


def household_plan():
    return QuestPlan(quests=[
        {"title": "Clear one spot", "action": "Clear your desk.", "completion_criteria": "The selected desk area is clear of loose items.", "estimated_minutes": 3, "difficulty": "easy"},
        {"title": "Return stored items", "action": "Put remaining desk items in the existing storage beside it.", "completion_criteria": "The remaining items are stored beside the desk.", "estimated_minutes": 3, "difficulty": "easy"},
        {"title": "Wipe the surface", "action": "Wipe the cleared desk area with a cloth you already have.", "completion_criteria": "The cleared desk area is wiped.", "estimated_minutes": 2, "difficulty": "easy"},
    ])


class EverydayPolicyTests(unittest.TestCase):
    def test_short_physical_actions_and_observable_outcomes_are_valid(self):
        context = QuestlineContext(goal="Tidy my desk using existing storage", available_minutes=5, energy="low")
        self.assertEqual(deterministic_issues(household_plan(), context, GroundingContext(summary=context.goal)), ())

    def test_generic_cooking_needs_one_fact_but_named_ingredients_do_not(self):
        context = QuestlineContext(goal="i want to make a dish but im tired", available_minutes=10, energy="low")
        self.assertEqual(clarification_question(context), "Which dish or ingredients you already have would you like to use?")
        context = context.model_copy(update={"contextual_notes": "Make a sandwich using bread, tomato and cheese already here."})
        self.assertIsNone(clarification_question(context))

    def test_specific_programming_skill_topic_does_not_repeat_a_question(self):
        context = QuestlineContext(goal="Improve my programming skills with Python list comprehensions", available_minutes=15, energy="low")
        self.assertIsNone(clarification_question(context))

    def test_develop_and_record_counted_tests_do_not_false_reject(self):
        context = QuestlineContext(goal="Implement binary search in C++ and record two test cases", available_minutes=20, energy="low")
        raw = plan_data()
        raw["quests"][0].update(action="Read the binary search requirements in the local brief.", completion_criteria="A written list contains the binary search requirements.")
        raw["quests"][1].update(action="Develop two test cases for the binary search function in C++.", completion_criteria="Two test cases are written in the local file.")
        raw["quests"][2].update(action="Record the binary search test results locally.", completion_criteria="A table contains both recorded test results.")
        self.assertNotIn("duplicate_or_contradiction", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_python_is_grounded_by_explicit_fastapi_stack_only(self):
        raw = plan_data(); raw["quests"][1]["action"] += " Use the existing Python test file."
        context = QuestlineContext(goal="Write three unit tests for my FastAPI login endpoint", available_minutes=20, energy="low")
        self.assertNotIn("unsupported_assumption", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))
        context = context.model_copy(update={"goal": "Write three tests for my existing login endpoint"})
        self.assertIn("unsupported_assumption", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_short_medium_start_not_rejected_solely_for_low_energy(self):
        raw = plan_data(); raw["quests"][0]["difficulty"] = "medium"
        context = QuestlineContext(goal="Write three unit tests for my FastAPI login endpoint", available_minutes=20, energy="low")
        self.assertNotIn("inappropriate_difficulty", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_explicit_no_heat_only_ingredients_and_vegetarian_constraints(self):
        context = QuestlineContext(goal="Make a no-cook vegetarian snack using only bread, tomato and cheese; no stove and no shopping", available_minutes=10, energy="low")
        raw = household_plan().model_dump()
        raw["quests"][0].update(action="Assemble bread, tomato and cheese on a plate without heat.", completion_criteria="Bread, tomato and cheese are assembled on the plate.")
        self.assertNotIn("explicit_constraint_violated", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))
        for action in ("Heat the bread on the stove.", "Add chicken to the snack.", "Add butter to the bread."):
            with self.subTest(action=action):
                raw["quests"][0]["action"] = action
                self.assertIn("explicit_constraint_violated", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))
        raw["quests"][0]["action"] = "Buy bread and cheese for the snack."
        self.assertIn("external_dependency", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_physical_arrangement_and_ingredient_plurals_are_observable(self):
        context = QuestlineContext(goal="Make a snack using only bread, tomatoes and cheese", available_minutes=10, energy="low")
        raw = household_plan().model_dump()
        raw["quests"][0].update(action="Arrange tomato and cheese on the bread.", completion_criteria="Tomato and cheese are evenly distributed on the bread.")
        issues = deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal))
        self.assertNotIn("unobservable_criteria", issues)
        self.assertNotIn("explicit_constraint_violated", issues)

    def test_physical_serving_is_observable_without_document_vocabulary(self):
        context = QuestlineContext(goal="Make a sandwich using bread and cheese", available_minutes=10, energy="low")
        raw = household_plan().model_dump()
        for criteria in ("The sandwich is on a plate and ready for serving.", "The snack is ready for consumption."):
            raw["quests"][0].update(action="Serve the assembled sandwich.", completion_criteria=criteria)
            self.assertNotIn("unobservable_criteria", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_explicit_no_auth_and_existing_runner_constraints_remain_hard(self):
        context = QuestlineContext(goal="Build book records in my existing FastAPI project; no login or deployment. Use existing test runner and fixtures.", available_minutes=20, energy="medium")
        raw = plan_data()
        for action in ("Implement login for book records.", "Deploy the book records app.", "Install a local test runner using pytest."):
            with self.subTest(action=action):
                raw["quests"][0]["action"] = action
                self.assertIn("explicit_constraint_violated", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_unknown_presentation_topic_clarifies_but_specific_ai_goal_does_not(self):
        context = QuestlineContext(goal="I need to present a complex topic that I know nothing about.", available_minutes=240, energy="low")
        self.assertEqual(clarification_question(context), "What is the presentation topic and the main result you need to communicate?")
        context = context.model_copy(update={"goal": "Prepare a 5-minute introduction to artificial intelligence for my classmates. Research the basics, create three slides, and practice."})
        self.assertIsNone(clarification_question(context))
        context = context.model_copy(update={"goal": "Present a complex topic about SQLite transactions"})
        self.assertIsNone(clarification_question(context))

    def test_explicit_presentation_practice_and_slide_count_cannot_disappear(self):
        context = QuestlineContext(goal="Prepare an introduction to AI, create three slides and practice", available_minutes=60, energy="medium")
        raw = household_plan().model_dump()
        for index, q in enumerate(raw["quests"]):
            q.update(title=f"Slide {index+1}", action=f"Create the {('first','second','third')[index]} slide about AI.", completion_criteria="The slide contains an AI definition and example.")
        issues = deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal))
        self.assertIn("unrelated", issues)
        self.assertNotIn("duplicate_or_contradiction", issues)
        raw["quests"][2].update(action="Create the third slide, then practice the AI introduction aloud.", completion_criteria="The third slide is saved and a five-minute rehearsal run is recorded.")
        self.assertNotIn("unrelated", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))
        raw["quests"][2]["action"] = "Practice the AI introduction aloud."
        raw["quests"][2]["completion_criteria"] = "A rehearsal run is recorded."
        self.assertIn("duplicate_or_contradiction", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_prohibitions_are_not_external_requirements(self):
        context = QuestlineContext(goal="Write three unit tests for my FastAPI login endpoint", available_minutes=20, energy="low")
        raw = plan_data(); raw["quests"][0]["action"] += " Do not download tools; avoid online tutorials."
        self.assertNotIn("external_dependency", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))

    def test_raw_food_tasting_is_not_accepted_as_an_observable_quest(self):
        context = QuestlineContext(goal="Prepare a simple meal with flour", available_minutes=10, energy="low")
        raw = household_plan().model_dump(); raw["quests"][0]["action"] = "Taste the raw flour mixture."
        self.assertIn("unsafe_food_instruction", deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal)))


# Reuse the existing temporary SQLite/Ollama helpers, without rediscovering their
# inherited test methods as a second copy of the whole original suite.
class SharedRetryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = helpers.PipelineTests.asyncSetUp
    asyncTearDown = helpers.PipelineTests.asyncTearDown
    adapter = helpers.PipelineTests.adapter
    request = helpers.PipelineTests.request
    count = helpers.PipelineTests.count
    assert_error = helpers.PipelineTests.assert_error

    async def test_minor_action_warning_saves_once_without_correction(self):
        raw = plan_data(); raw["quests"][0]["action"] = "Work on it. PRIVATE_REJECTED_OUTPUT"
        adapter = self.adapter([raw])
        body = self.request()
        result = await self.service.generate(body, str(uuid4()), adapter)
        self.assertEqual(len(result.generation.attempts), 1)
        self.assertTrue(result.generation.attempts[0].validation_success)
        self.assertEqual(result.generation.assessments[0].warnings, ("vague_action",))
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
        self.assertEqual(len(self.calls), 1)

    async def test_format_and_essential_failures_share_one_retry(self):
        import httpx
        raw = plan_data(); raw["quests"][0]["action"] = "Download an online tutorial and create an account."
        adapter = self.adapter([httpx.Response(200, json={"response": "{", "done": True}), raw])
        await self.assert_error("AI_SEMANTIC_REJECTED", self.service.generate(self.request(), str(uuid4()), adapter))
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.count(Questline), 0)
        self.assertEqual(self.quests.get_profile().total_xp, 0)

    async def test_uncertain_review_cannot_trigger_correction(self):
        adapter = self.adapter([plan_data(), approval(acceptable=False, confidence="low"), plan_data(), approval()])
        result = await self.service.generate(self.request(), str(uuid4()), adapter)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(result.review)
        self.assertEqual(result.generation.attempts[0].semantic_codes, ())
        self.assertEqual(self.count(Questline), 1)

    async def test_unavailable_reviewer_does_not_block_generation(self):
        decision = approval(acceptable=False, confidence="low")
        body = self.request()
        from unittest.mock import patch
        from app.ollama import OllamaClient
        with patch.object(OllamaClient, "review_quest_plan", side_effect=AssertionError("Reviewer unavailable")):
            result = await self.service.generate(body, str(uuid4()), self.adapter([plan_data()]))
        self.assertIsNone(result.review)
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "consumed")
        self.assertEqual(self.count(Questline), 1)

    async def test_unknown_presentation_topic_blocks_inference_and_preserves_check_in(self):
        from app.schemas import CheckInStart
        first, _ = self.service.submit(CheckInStart(mode="start", goal="I need to present a complex topic that I know nothing about.", available_minutes=240, energy="low"), str(uuid4()))
        self.assertEqual(first.status, "needs_follow_up")
        self.assertIn("topic", first.question)
        await self.assert_error("CHECK_IN_NOT_READY", self.service.generate(self.request(first), str(uuid4()), self.adapter([])))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.service.get(first.id).context.goal, first.context.goal)
        self.assertEqual(self.count(Questline), 0)

    async def test_missing_practice_is_corrected_before_presentation_persistence(self):
        from app.schemas import CheckInStart
        first, _ = self.service.submit(CheckInStart(mode="start", goal="Prepare an introduction to artificial intelligence, create three slides and practice", available_minutes=60, energy="medium"), str(uuid4()))
        raw = {"quests": [
            {"title": "Research AI", "action": "Review artificial intelligence basics using local knowledge and write definitions.", "completion_criteria": "A summary contains AI definitions.", "estimated_minutes": 10, "difficulty": "easy"},
            {"title": "Create slides", "action": "Create three slides about artificial intelligence using an existing local tool.", "completion_criteria": "Three slides are saved locally.", "estimated_minutes": 20, "difficulty": "medium"},
            {"title": "Check slides", "action": "Review the three slides for missing definitions.", "completion_criteria": "A checklist of the three slides is written.", "estimated_minutes": 5, "difficulty": "easy"},
        ]}
        import copy
        fixed = copy.deepcopy(raw)
        fixed["quests"][2].update(title="Practice the introduction", action="Practice the artificial intelligence introduction aloud once with a timer.", completion_criteria="One rehearsal run and its duration are recorded locally.")
        result = await self.service.generate(self.request(first), str(uuid4()), self.adapter([raw, fixed, approval()]))
        self.assertEqual(result.generation.attempts[0].semantic_codes, ("unrelated",))
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.quests.get_profile().total_xp, 0)

    async def test_observable_household_plan_can_be_persisted_without_xp(self):
        from app.schemas import CheckInStart
        first, _ = self.service.submit(CheckInStart(mode="start", goal="Tidy my desk using existing storage", available_minutes=5, energy="low"), str(uuid4()))
        result = await self.service.generate(self.request(first), str(uuid4()), self.adapter([household_plan().model_dump(), approval()]))
        self.assertEqual(result.view.progress.total_count, 3)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
