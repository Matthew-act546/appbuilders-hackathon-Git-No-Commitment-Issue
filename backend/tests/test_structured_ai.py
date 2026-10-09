import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.benchmark_ai import scenarios, summarize
from app.config import Settings
from app.ollama import GENERATION_OPTIONS, OllamaClient, QuestGenerationError
from app.schemas import CheckInInput, QuestPlan


def valid_plan():
    return {"quests": [
        {"title": "Scout the requirements", "action": "Read the assignment brief and list its required outputs.",
         "completion_criteria": "A checklist of required outputs exists.", "estimated_minutes": 10, "difficulty": "easy"},
        {"title": "Build one piece", "action": "Implement the smallest required function.",
         "completion_criteria": "The function runs on one sample input.", "estimated_minutes": 30, "difficulty": "medium", "hint": None},
        {"title": "Check the result", "action": "Run the provided test cases and note failures.",
         "completion_criteria": "Each provided test has a recorded pass or fail.", "estimated_minutes": 20, "difficulty": "medium"},
    ]}


def outer(plan=None, **overrides):
    return {"response": json.dumps(plan if plan is not None else valid_plan()), "done": True, "done_reason": "stop", **overrides}


class ProposalSchemaTests(unittest.TestCase):
    def test_valid_strict_json_and_optional_hint(self):
        proposal = valid_plan()
        proposal["quests"][0]["title"] = "  Scout the requirements  "
        plan = QuestPlan.model_validate_json(json.dumps(proposal), context={"available_minutes": 20})
        self.assertEqual(plan.quests[0].title, "Scout the requirements")
        self.assertIsNone(plan.quests[0].hint)
        self.assertGreater(sum(quest.estimated_minutes for quest in plan.quests), 20)

    def test_invalid_fields_and_strict_types(self):
        mutations = [
            ("missing", lambda p: p["quests"][0].pop("completion_criteria")),
            ("difficulty", lambda p: p["quests"][0].update(difficulty="impossible")),
            ("empty action", lambda p: p["quests"][0].update(action=" \n ")),
            ("empty title", lambda p: p["quests"][0].update(title="")),
            ("empty criteria", lambda p: p["quests"][0].update(completion_criteria=" ")),
            ("empty hint", lambda p: p["quests"][0].update(hint=" ")),
            ("zero", lambda p: p["quests"][0].update(estimated_minutes=0)),
            ("negative", lambda p: p["quests"][0].update(estimated_minutes=-1)),
            ("string integer", lambda p: p["quests"][0].update(estimated_minutes="10")),
            ("float integer", lambda p: p["quests"][0].update(estimated_minutes=10.0)),
            ("boolean integer", lambda p: p["quests"][0].update(estimated_minutes=True)),
            ("numeric action", lambda p: p["quests"][0].update(action=123)),
            ("too few", lambda p: p.update(quests=p["quests"][:1])),
            ("too many", lambda p: p.update(quests=p["quests"] * 3)),
            ("duplicate title", lambda p: p["quests"][1].update(title=" SCOUT THE REQUIREMENTS ")),
            ("duplicate action", lambda p: p["quests"][1].update(action=p["quests"][0]["action"].upper())),
            ("first over capacity", lambda p: p["quests"][0].update(estimated_minutes=21)),
            ("oversized title", lambda p: p["quests"][0].update(title="x" * 101)),
            ("root authority", lambda p: p.update(profile={"total_xp": 1000})),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                plan = valid_plan(); mutate(plan)
                with self.assertRaises(ValidationError):
                    QuestPlan.model_validate_json(json.dumps(plan), context={"available_minutes": 20})
        for authority in ("id", "xp", "level", "status", "unlocked", "completed_at", "plan_revision", "plan_version", "profile"):
            with self.subTest(authority=authority):
                plan = valid_plan(); plan["quests"][0][authority] = "untrusted"
                with self.assertRaises(ValidationError):
                    QuestPlan.model_validate_json(json.dumps(plan))

    def test_malformed_json_and_code_fences_are_rejected(self):
        for raw in ("{", "not JSON", "```json\n" + json.dumps(valid_plan()) + "\n```"):
            with self.subTest(raw_type=raw[:8]), self.assertRaises(ValidationError):
                QuestPlan.model_validate_json(raw)

    def test_input_validation_and_timezone(self):
        parsed = CheckInInput.model_validate_json('{"goal":" Draft slides ","available_minutes":15,"energy":"low","deadline":"2026-10-09T23:59:00+08:00"}')
        self.assertEqual(parsed.goal, "Draft slides")
        self.assertEqual(parsed.deadline.utcoffset().total_seconds(), 0)
        for patch in ({"goal": " "}, {"available_minutes": 0}, {"available_minutes": True},
                      {"available_minutes": "15"}, {"energy": "exhausted"}, {"deadline": "2026-10-09T23:59:00"}, {"xp": 10}):
            data = {"goal": "Draft slides", "available_minutes": 15, "energy": "low", **patch}
            with self.subTest(patch=tuple(patch)), self.assertRaises(ValidationError):
                CheckInInput.model_validate_json(json.dumps(data))


class StructuredGenerationTests(unittest.IsolatedAsyncioTestCase):
    async def generate(self, responses, *, model="qwen3:1.7b", timeout=120, attempt_timeout=60):
        self.requests = []

        def handler(request):
            self.requests.append(request)
            response = responses[len(self.requests) - 1]
            if isinstance(response, Exception):
                raise response
            return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:11434") as client:
            adapter = OllamaClient(client, Settings(_env_file=None, ollama_model=model))
            return await adapter.generate_quest_plan(CheckInInput(goal="Finish an assignment", available_minutes=20, energy="low"),
                                                      timeout=timeout, attempt_timeout=attempt_timeout)

    async def test_valid_native_schema_request_and_non_thinking(self):
        result = await self.generate([outer(load_duration=123, thinking="")])
        request = self.requests[0]; payload = json.loads(request.content)
        self.assertEqual(request.url.path, "/api/generate")
        self.assertEqual(payload["format"], QuestPlan.model_json_schema())
        self.assertFalse(payload["format"]["additionalProperties"])
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"], GENERATION_OPTIONS)
        self.assertEqual(request.extensions["timeout"]["connect"], 3)
        self.assertLessEqual(request.extensions["timeout"]["read"], 60)
        self.assertEqual(len(result.attempts), 1)
        self.assertTrue(result.attempts[0].validation_success)
        self.assertFalse(result.attempts[0].ollama_metrics["thinking_present"])

    async def test_backup_is_explicit_and_thinking_flag_omitted(self):
        await self.generate([outer()], model="qwen2.5:1.5b")
        payload = json.loads(self.requests[0].content)
        self.assertEqual(payload["model"], "qwen2.5:1.5b")
        self.assertNotIn("think", payload)

    async def test_invalid_output_then_valid_retry_is_sanitized(self):
        invalid = valid_plan(); invalid["quests"][0].pop("action")
        invalid["quests"][0]["private_invalid_field"] = "DO_NOT_ECHO_INVALID_MODEL_OUTPUT"
        result = await self.generate([outer(invalid), outer()])
        self.assertEqual(len(result.attempts), 2)
        self.assertFalse(result.attempts[0].validation_success)
        self.assertTrue(result.attempts[1].validation_success)
        retry = json.loads(self.requests[1].content)["prompt"]
        self.assertIn("Correction:", retry)
        self.assertIn("extra_forbidden", retry)
        self.assertNotIn("DO_NOT_ECHO_INVALID_MODEL_OUTPUT", retry)

    async def test_two_invalid_responses_exhaust_exactly_one_retry(self):
        with self.assertRaises(QuestGenerationError) as raised:
            await self.generate([outer(response="{"), outer(response="not JSON")])
        error = raised.exception
        self.assertEqual(error.code, "AI_INVALID_OUTPUT")
        self.assertTrue(error.retryable)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(len(error.attempts), 2)
        self.assertTrue(all(not attempt.validation_success for attempt in error.attempts))
        self.assertNotIn("not JSON", str(error))

    async def test_schema_and_domain_failures_trigger_only_one_retry(self):
        for patch in ({"difficulty": "invalid"}, {"action": " "}, {"estimated_minutes": 0},
                      {"estimated_minutes": -1}, {"xp": 1000}, {"estimated_minutes": 21}):
            invalid = valid_plan(); invalid["quests"][0].update(patch)
            with self.subTest(field=tuple(patch)), self.assertRaises(QuestGenerationError) as raised:
                await self.generate([outer(invalid), outer(invalid)])
            self.assertEqual(raised.exception.code, "AI_INVALID_OUTPUT")
            self.assertEqual(len(self.requests), 2)
        for quests in (valid_plan()["quests"][:1], valid_plan()["quests"] * 3):
            with self.subTest(count=len(quests)), self.assertRaises(QuestGenerationError):
                await self.generate([outer({"quests": quests}), outer({"quests": quests})])
            self.assertEqual(len(self.requests), 2)

    async def test_incomplete_or_non_string_response_is_never_accepted(self):
        for patch in ({"done": False}, {"done_reason": "length"}, {"response": 123}):
            with self.subTest(field=tuple(patch)), self.assertRaises(QuestGenerationError):
                await self.generate([outer(**patch), outer(**patch)])
            self.assertEqual(len(self.requests), 2)

    async def test_connection_failure_and_timeout_do_not_retry(self):
        for exception, code in ((httpx.ConnectError("private error text"), "OLLAMA_UNAVAILABLE"),
                                (httpx.ReadTimeout("private error text"), "AI_TIMEOUT")):
            with self.subTest(code=code), self.assertRaises(QuestGenerationError) as raised:
                await self.generate([exception])
            self.assertEqual(raised.exception.code, code)
            self.assertIsNone(raised.exception.attempts[0].validation_success)
            self.assertEqual(len(self.requests), 1)
            self.assertNotIn("private error text", str(raised.exception))

    async def test_http_and_outer_json_failures_are_distinct_from_plan_validation(self):
        for response, code in ((httpx.Response(404, json={"error": "missing model"}), "MODEL_UNAVAILABLE"),
                               (httpx.Response(500, json={"error": "upstream"}), "AI_UPSTREAM_ERROR"),
                               (httpx.Response(200, text="invalid envelope"), "AI_UPSTREAM_ERROR")):
            with self.subTest(code=code), self.assertRaises(QuestGenerationError) as raised:
                await self.generate([response])
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(len(self.requests), 1)

    async def test_whole_operation_budget_includes_retry(self):
        calls = []
        clock = {"seconds": 0.0}

        def slow(request):
            calls.append(request)
            if len(calls) == 1:
                clock["seconds"] += 0.04
                return httpx.Response(200, json=outer(response="{"))
            clock["seconds"] += 0.02
            raise httpx.ReadTimeout("Simulated exhausted remaining budget", request=request)

        with patch("app.ollama.perf_counter", side_effect=lambda: clock["seconds"]):
            async with httpx.AsyncClient(transport=httpx.MockTransport(slow), base_url="http://localhost:11434") as client:
                adapter = OllamaClient(client, Settings(_env_file=None))
                with self.assertRaises(QuestGenerationError) as raised:
                    await adapter.generate_quest_plan(CheckInInput(goal="Test", available_minutes=20, energy="low"),
                                                     timeout=0.06, attempt_timeout=1)
        self.assertEqual(raised.exception.code, "AI_TIMEOUT")
        self.assertEqual(len(calls), 2)
        self.assertLess(calls[1].extensions["timeout"]["read"], calls[0].extensions["timeout"]["read"])
        self.assertAlmostEqual(raised.exception.latency_seconds, 0.06)

    async def test_expired_budget_prevents_starting_a_retry(self):
        clock = {"seconds": 0.0}
        calls = []

        def handler(request):
            calls.append(request)
            clock["seconds"] += 2
            return httpx.Response(200, json=outer(response="{"))

        with patch("app.ollama.perf_counter", side_effect=lambda: clock["seconds"]):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434") as client:
                adapter = OllamaClient(client, Settings(_env_file=None))
                with self.assertRaises(QuestGenerationError) as raised:
                    await adapter.generate_quest_plan(CheckInInput(goal="Test", available_minutes=20, energy="low"), timeout=1)
        self.assertEqual(raised.exception.code, "AI_TIMEOUT")
        self.assertEqual(len(calls), 1)

    async def test_valid_result_arriving_after_budget_is_discarded(self):
        clock = {"seconds": 0.0}

        def handler(request):
            clock["seconds"] += 2
            return httpx.Response(200, json=outer())

        with patch("app.ollama.perf_counter", side_effect=lambda: clock["seconds"]):
            async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434") as client:
                adapter = OllamaClient(client, Settings(_env_file=None))
                with self.assertRaises(QuestGenerationError) as raised:
                    await adapter.generate_quest_plan(CheckInInput(goal="Test", available_minutes=20, energy="low"), timeout=1)
        self.assertEqual(raised.exception.code, "AI_TIMEOUT")
        self.assertEqual(len(raised.exception.attempts), 1)

    async def test_nonlocal_url_and_invalid_budgets_rejected_before_inference(self):
        async with httpx.AsyncClient(base_url="https://remote.example") as client:
            adapter = OllamaClient(client, Settings(_env_file=None))
            with self.assertRaises(ValueError):
                await adapter.generate_quest_plan(CheckInInput(goal="Test", available_minutes=20, energy="low"))
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=str(timeout)), self.assertRaises(ValueError):
                await self.generate([], timeout=timeout)
            self.assertEqual(self.requests, [])

    async def test_deadline_math_is_python_owned_and_reference_is_aware(self):
        payloads = []

        def handler(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json=outer())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://localhost:11434") as client:
            adapter = OllamaClient(client, Settings(_env_file=None))
            context = CheckInInput(goal="Finish assignment", available_minutes=20, energy="low",
                                   deadline=datetime(2026, 10, 9, 14, tzinfo=timezone.utc))
            await adapter.generate_quest_plan(context, reference_time=datetime(2026, 10, 9, 12, tzinfo=timezone.utc))
            self.assertIn("Deadline minutes remaining (Python): 120", payloads[0]["prompt"])
            await adapter.generate_quest_plan(context, reference_time=datetime(2026, 10, 9, 15, tzinfo=timezone.utc))
            self.assertIn("Deadline minutes remaining (Python): -60", payloads[1]["prompt"])
            with self.assertRaises(ValueError):
                await adapter.generate_quest_plan(context, reference_time=datetime(2026, 10, 9, 12))
            self.assertEqual(len(payloads), 2)


class BenchmarkTests(unittest.TestCase):
    def test_five_scenarios_and_deadlines_are_deterministic(self):
        reference = datetime(2026, 10, 9, 12, tzinfo=timezone.utc)
        cases = scenarios(reference)
        self.assertEqual([name for name, _ in cases], list("ABCDE"))
        self.assertIsNone(cases[2][1].deadline)
        self.assertEqual(cases[0][1].deadline.day, 10)
        self.assertEqual(cases[3][1].deadline.day, 9)

    def test_statistics_distinguish_first_attempt_and_retry_success(self):
        rows = [{"validation_success": True, "retry_count": 0, "latency_seconds": 2,
                 "attempts": [{"validation_success": True}]},
                {"validation_success": True, "retry_count": 1, "latency_seconds": 4,
                 "attempts": [{"validation_success": False}, {"validation_success": True}]},
                {"validation_success": False, "retry_count": 0, "latency_seconds": 6,
                 "attempts": [{"validation_success": None}]}]
        summary = summarize(rows)
        self.assertEqual(summary["first_attempt_successes"], 1)
        self.assertEqual(summary["successes_after_retry"], 1)
        self.assertEqual(summary["inference_attempts"], 4)
        self.assertEqual(summary["schema_evaluated_attempts"], 3)
        self.assertEqual(summary["schema_validity_rate"], 0.5)
        self.assertEqual(summary["median_latency_seconds"], 4)
        self.assertEqual(summary["maximum_latency_seconds"], 6)


if __name__ == "__main__":
    unittest.main()
