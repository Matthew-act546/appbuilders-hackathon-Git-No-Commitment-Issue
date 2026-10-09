"""Regression evidence for Phase 3C classifications and bounded scoped repairs."""
import unittest
from uuid import uuid4
from pydantic import ValidationError
from app.models import Questline
from app.ollama import apply_content_repair, content_repair_schema, semantic_review_schema
from app.quality import (RepairTarget, clarification_question, classify_review, deterministic_issues, repair_targets)
from app.schemas import (CheckInStart, GroundingContext, QuestPlan, QuestPlanRepair, QuestlineContext, ReplanRequest, SemanticReview)
import test_check_in as helpers
from test_check_in import approval, plan_data


def presentation():
    return {"quests": [
        {"title": "Find the basics", "action": "Summarize artificial intelligence definitions from local knowledge.", "completion_criteria": "A summary contains an AI definition and one everyday example.", "estimated_minutes": 10, "difficulty": "easy"},
        {"title": "Build the slides", "action": "Create three slides about artificial intelligence using an existing local tool.", "completion_criteria": "Three slides contain the introduction, example and summary.", "estimated_minutes": 20, "difficulty": "medium"},
        {"title": "Try the delivery", "action": "Complete one timed rehearsal of the AI introduction aloud and record its duration.", "completion_criteria": "One timed rehearsal is completed and its duration is recorded.", "estimated_minutes": 5, "difficulty": "easy"},
    ]}


class ClassificationTests(unittest.TestCase):
    def context(self, goal="Prepare a presentation about artificial intelligence with exactly three slides and one timed rehearsal"):
        return QuestlineContext(goal=goal, available_minutes=45, energy="medium")

    def issues(self, raw, context=None):
        context = context or self.context()
        return deterministic_issues(QuestPlan(**raw), context, GroundingContext(summary=context.goal))

    def test_optional_existing_tool_example_is_not_a_required_dependency(self):
        raw = presentation()
        raw["quests"][1]["action"] += " A tool like PowerPoint is optional if already available."
        self.assertNotIn("unsupported_assumption", self.issues(raw))
        raw["quests"][1]["action"] = "Create three slides using PowerPoint."
        self.assertIn("unsupported_assumption", self.issues(raw))

    def test_required_tool_stays_blocked_and_explicit_optional_download_warns(self):
        raw = presentation()
        raw["quests"][1]["action"] = "Use a tool like PowerPoint; PowerPoint is required."
        self.assertIn("unsupported_assumption", self.issues(raw))
        raw["quests"][1]["action"] = "Optional: download a slide editor to create three slides."
        self.assertNotIn("external_dependency", self.issues(raw))
        self.assertIn("optional_tool_suggestion", self.issues(raw))

    def test_printed_loop_output_is_observable_but_understanding_is_not(self):
        context = self.context("Study Python loops for tomorrow's quiz")
        raw = plan_data()
        for q in raw["quests"]:
            q.update(action="Write a Python loop in the local editor.", completion_criteria="The loop prints numbers from 1 to 10 in order.")
        # Distinctness is separately enforced by the proposal schema.
        raw["quests"][1]["action"] = "Run a Python loop that prints a greeting five times."
        raw["quests"][2]["action"] = "Run a Python while loop and inspect its output."
        raw["quests"][1]["completion_criteria"] = "The loop prints a greeting five times."
        raw["quests"][2]["completion_criteria"] = "The loop displays the computed sum."
        self.assertNotIn("unobservable_criteria", self.issues(raw, context))
        raw["quests"][0]["completion_criteria"] = "I understand Python loops."
        self.assertIn("unobservable_criteria", self.issues(raw, context))

    def test_unknown_food_and_format_only_presentation_require_one_fact(self):
        for goal in ("I want to make something simple to eat, but I'm tired.", "Prepare a short presentation with exactly three slides and one timed rehearsal."):
            self.assertIsNotNone(clarification_question(self.context(goal)))
        self.assertIsNone(clarification_question(self.context("Prepare a 5-minute introduction to artificial intelligence for my classmates. Research the basics, create three slides, and practice.")))

    def test_available_food_does_not_license_extra_ingredients(self):
        context = self.context("Make a no-cook sandwich with bread and cheese already available")
        raw = presentation()
        raw["quests"][0].update(action="Assemble bread and cheese into a sandwich.", completion_criteria="The sandwich is assembled on a plate.")
        self.assertNotIn("unsupported_assumption", self.issues(raw, context))
        raw["quests"][0]["action"] = "Add ham and lettuce to the bread and cheese sandwich."
        self.assertIn("unsupported_assumption", self.issues(raw, context))

    def test_desk_does_not_license_unmentioned_special_supplies(self):
        context = self.context("Clean my desk before studying")
        raw = presentation()
        raw["quests"][0].update(action="Collect a vacuum cleaner and disinfectant wipes from the desk drawer.", completion_criteria="Supplies are visible on the desk.")
        self.assertIn("unsupported_assumption", self.issues(raw, context))
        raw["quests"][0]["action"] = "Clear the items from the desk area needed for studying."
        self.assertNotIn("unsupported_assumption", self.issues(raw, context))

    def test_named_loop_topic_must_not_be_replaced_with_unrelated_work(self):
        self.assertIn("unrelated", self.issues(presentation(), self.context("Study Python loops for tomorrow's quiz")))

    def test_missing_practice_count_or_timed_requirement_remain_hard(self):
        raw = presentation(); raw["quests"][2]["action"] = "Review the finished AI slides."; raw["quests"][2]["completion_criteria"] = "Slides contain the required definitions."
        self.assertIn("unrelated", self.issues(raw))
        raw = presentation(); raw["quests"][1]["action"] = "Create two slides about AI."; raw["quests"][1]["completion_criteria"] = "Two slides are saved."
        self.assertIn("duplicate_or_contradiction", self.issues(raw))
        raw = presentation(); raw["quests"][2]["action"] = "Complete two timed rehearsals of the AI introduction."; raw["quests"][2]["completion_criteria"] = "Two rehearsal durations are recorded."
        self.assertIn("duplicate_or_contradiction", self.issues(raw))

    def test_research_criterion_later_slide_is_a_sequencing_warning(self):
        raw = presentation(); raw["quests"][0]["completion_criteria"] = "The slide contains the researched definition."
        self.assertIn("sequencing_imperfection", self.issues(raw))

    def test_duplicate_criteria_repairs_only_the_later_quest(self):
        raw = presentation(); raw["quests"][2]["completion_criteria"] = raw["quests"][1]["completion_criteria"]
        self.assertIn("unobservable_criteria", self.issues(raw))
        self.assertEqual(repair_targets(QuestPlan(**raw), ("unobservable_criteria",))[0].quest_index, 2)

    def test_visual_grading_is_repairable_not_an_observable_result(self):
        raw = presentation(); raw["quests"][1]["completion_criteria"] = "Three slides are visually engaging and formatted correctly."
        self.assertIn("unobservable_criteria", self.issues(raw))

    def test_repair_targets_identify_exact_quest_and_field_without_relaxing_hard_failure(self):
        raw = presentation(); raw["quests"][1]["completion_criteria"] = "Feel confident."
        plan = QuestPlan(**raw)
        self.assertEqual(repair_targets(plan, ("unobservable_criteria",)), (RepairTarget(1, ("completion_criteria",), ("unobservable_criteria",)),))
        self.assertEqual(repair_targets(plan, ("unobservable_criteria", "external_dependency")), ())

    def test_borderline_review_opinion_is_advisory_but_known_capacity_is_hard(self):
        plan = QuestPlan(**presentation())
        review = SemanticReview(**approval(acceptable=False, issues=["implausible_estimate", "inappropriate_difficulty"]))
        self.assertEqual(classify_review(plan, review), ((), ()))
        raw = presentation(); raw["quests"][0]["estimated_minutes"] = 46
        self.assertIn("implausible_estimate", self.issues(raw))

    def test_review_optional_tool_evidence_is_checked_not_blindly_believed(self):
        raw = presentation(); raw["quests"][1]["action"] += " Use an existing tool like PowerPoint if available."
        plan = QuestPlan(**raw)
        review = SemanticReview(**approval(acceptable=False, issues=["unsupported_assumption"], findings=[{"quest_index": 1, "field": "action", "code": "unsupported_assumption", "quote": "tool like PowerPoint"}]))
        self.assertEqual(classify_review(plan, review), ((), ()))
        review.findings[0].quote = "Not an actual candidate quote"
        self.assertEqual(classify_review(plan, review)[0], ("unsupported_assumption",))
        self.assertEqual(classify_review(plan, SemanticReview(**approval(acceptable=False, confidence="low")))[0], ("uncertain_review",))

    def test_localized_review_repairs_only_quoted_field(self):
        raw = presentation(); raw["quests"][2]["completion_criteria"] = "A rehearsal summary is saved."
        plan = QuestPlan(**raw)
        review = SemanticReview(**approval(acceptable=False, issues=["unobservable_criteria"], findings=[{"quest_index": 2, "field": "completion_criteria", "code": "unobservable_criteria", "quote": "A rehearsal summary is saved."}]))
        self.assertEqual(classify_review(plan, review)[1][0].fields, ("completion_criteria",))


class PatchBoundaryTests(unittest.TestCase):
    def test_native_review_cannot_accept_and_emit_rejection_findings(self):
        schema = semantic_review_schema()
        accepted = schema["anyOf"][0]["properties"]
        self.assertTrue(accepted["acceptable"]["const"])
        self.assertEqual(accepted["issues"]["const"], [])
        self.assertEqual(accepted["findings"]["const"], [])
        self.assertEqual(schema["anyOf"][1]["properties"]["findings"]["maxItems"], 1)
        self.assertEqual(schema["anyOf"][2]["properties"]["confidence"]["const"], "low")

    def test_native_patch_schema_pins_exact_indexes_and_requested_fields(self):
        targets = (RepairTarget(0, ("completion_criteria",), ("unobservable_criteria",)), RepairTarget(2, ("action",), ("vague_action",)))
        schema = content_repair_schema(targets)
        items = schema["properties"]["repairs"]["prefixItems"]
        self.assertEqual(items[0]["properties"]["quest_index"]["const"], 0)
        self.assertEqual(items[1]["properties"]["quest_index"]["const"], 2)
        self.assertEqual(set(items[0]["properties"]), {"quest_index", "completion_criteria"})
        self.assertEqual(set(items[1]["properties"]), {"quest_index", "action"})
        self.assertFalse(items[0]["additionalProperties"])
        self.assertEqual(schema["properties"]["repairs"]["items"]["anyOf"], items)

    def test_patch_cannot_change_untargeted_content_or_add_authority(self):
        original = QuestPlan(**presentation()); before = original.model_dump()
        targets = (RepairTarget(1, ("completion_criteria",), ("unobservable_criteria",)),)
        patch = QuestPlanRepair(repairs=[{"quest_index": 1, "completion_criteria": "Three slides are saved locally."}])
        result = apply_content_repair(original, patch, targets, QuestPlan, 45)
        self.assertEqual(original.model_dump(), before)
        self.assertEqual(result.quests[0], original.quests[0])
        self.assertEqual(result.quests[2], original.quests[2])
        self.assertEqual(result.quests[1].action, original.quests[1].action)
        for value in [
            {"repairs": [{"quest_index": 1, "xp": 1000}]},
            {"repairs": [{"quest_index": 1, "status": "completed"}]},
            {"repairs": [{"quest_index": 1, "completion_criteria": ""}]},
            {"repairs": [{"quest_index": 6, "completion_criteria": "Three slides are saved."}]},
        ]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                QuestPlanRepair(**value)

    def test_wrong_duplicate_or_missing_targets_and_extra_fields_are_rejected(self):
        original = QuestPlan(**presentation()); targets = (RepairTarget(1, ("completion_criteria",), ("unobservable_criteria",)),)
        for repairs in [
            [{"quest_index": 0, "completion_criteria": "A summary exists."}],
            [{"quest_index": 1, "action": "Replace the topic."}],
            [{"quest_index": 1, "completion_criteria": "Slides saved."}, {"quest_index": 1, "completion_criteria": "Slides saved."}],
            [{"quest_index": 1}],
            [{"quest_index": 1, "action": "New action", "completion_criteria": "Slides saved."}],
        ]:
            with self.subTest(repairs=repairs), self.assertRaises(ValueError):
                apply_content_repair(original, QuestPlanRepair(repairs=repairs), targets, QuestPlan, 45)


class TargetedPipelineTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = helpers.PipelineTests.asyncSetUp
    asyncTearDown = helpers.PipelineTests.asyncTearDown
    adapter = helpers.PipelineTests.adapter
    request = helpers.PipelineTests.request
    count = helpers.PipelineTests.count
    assert_error = helpers.PipelineTests.assert_error

    async def test_subjective_criterion_saves_once_preserves_content_without_repair(self):
        raw = plan_data(); raw["quests"][0]["completion_criteria"] = "Feel confident PRIVATE_BAD_CRITERION"
        patch = {"repairs": [{"quest_index": 0, "completion_criteria": plan_data()["quests"][0]["completion_criteria"]}]}
        body, key = self.request(), str(uuid4())
        result = await self.service.generate(body, key, self.adapter([raw, patch, approval()]))
        self.assertEqual(result.generation.plan, QuestPlan(**raw))
        self.assertEqual(len(result.generation.attempts), 1)
        self.assertIn("unobservable_criteria", result.generation.assessments[0].warnings)
        self.assertEqual(self.count(Questline), 1)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
        replay = await self.service.generate(body, key, self.adapter([]))
        self.assertTrue(replay.replayed)
        self.assertEqual(len(self.calls), 1)

    async def test_correction_with_hard_violation_fails_and_same_intent_can_retry(self):
        raw = plan_data(); raw["quests"][0]["action"] = "Download an online tutorial and create an account."
        patch = raw
        body, key = self.request(), str(uuid4())
        error = await self.assert_error("AI_SEMANTIC_REJECTED", self.service.generate(body, key, self.adapter([raw, patch])))
        self.assertIn("external_dependency", error.details["codes"])
        self.assertEqual(self.count(Questline), 0)
        self.assertEqual(self.quests.get_profile().total_xp, 0)
        self.assertEqual(self.service.get(str(body.check_in_id)).status, "ready")
        await self.service.generate(body, key, self.adapter([plan_data(), approval()]))
        self.assertEqual(self.count(Questline), 1)

    async def test_wrong_correction_is_typed_recoverable_failure_with_two_attempts_only(self):
        raw = plan_data(); raw["quests"][0]["action"] = "Download an online tutorial."
        bad_patch = {"repairs": [{"quest_index": 1, "completion_criteria": "A file is saved."}]}
        error = await self.assert_error("AI_INVALID_OUTPUT", self.service.generate(self.request(), str(uuid4()), self.adapter([raw, bad_patch])))
        self.assertTrue(error.retryable)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.count(Questline), 0)

    async def test_warning_only_replan_preserves_completed_content_xp_and_revision_guards(self):
        initial = await self.service.generate(self.request(), str(uuid4()), self.adapter([plan_data(), approval()]))
        line = self.quests.complete_quest(initial.view.current_quest.id, 1).questline
        history = line.completed_quests[0].model_dump()
        raw = {"quests": plan_data()["quests"][1:]}
        raw["quests"][1]["completion_criteria"] = "Feel ready to finish."
        patch = {"repairs": [{"quest_index": 1, "completion_criteria": "A saved result lists the three tests and each pass or fail outcome."}]}
        body = ReplanRequest(expected_revision=line.revision, available_minutes=30, energy="medium")
        result = await self.service.generate(body, str(uuid4()), self.adapter([raw, patch, approval()]), line_id=line.id)
        self.assertEqual(result.view.completed_quests[0].model_dump(), history)
        self.assertEqual(self.quests.get_profile().total_xp, 10)
        self.assertEqual(result.view.plan_version, 2)
        self.assertEqual(len(result.generation.attempts), 1)
        self.assertIn("unobservable_criteria", result.generation.assessments[0].warnings)
        await self.assert_error("STALE_REVISION", self.service.generate(body, str(uuid4()), self.adapter([]), line_id=line.id))
