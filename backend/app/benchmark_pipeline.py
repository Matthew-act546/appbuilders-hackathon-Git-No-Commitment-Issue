"""Developer-only Phase 3 pipeline evidence using fictional inputs and a temp DB."""
import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import statistics
import tempfile
from time import perf_counter
from uuid import uuid4

import httpx

from .benchmark_ai import command_output, hardware_info, reference_time, scenarios
from .config import Settings
from .database import create_sqlite_engine
from .errors import QuestError
from .ollama import GENERATION_OPTIONS, PROMPT_VERSION, OllamaClient, require_local_url
from .quality import QUALITY_VERSION
from .schema import initialize_database
from .schemas import CheckInAnswer, CheckInStart, GenerateQuestlineRequest, ReplanRequest
from .services.check_in import CheckInService
from .services.quests import QuestService

ANSWERS = {
    "A": "Implement binary search on a sorted integer list in C++ using the supplied local assignment brief; record two test cases.",
    "C": "Practice Python list comprehensions by transforming three existing local example lists.",
    "D": "Explain how SQLite transactions prevent duplicate XP using the existing local project notes.",
    "E": "Manage book records with title and author using an existing FastAPI and SQLite project. Local CRUD only, no login or deployment.",
}


def fictional_cases(reference: datetime, hotfix_cases: bool = False) -> list[tuple[str, CheckInStart, str | None]]:
    result = [(case, CheckInStart(mode="start", **context.model_dump(),
              contextual_notes="Use local lecture notes on sorting and asymptotic analysis." if case == "B" else None), ANSWERS.get(case))
              for case, context in scenarios(reference)]
    result.extend([
        ("F", CheckInStart(mode="start", goal="Write three unit tests for my FastAPI login endpoint", available_minutes=20,
                           energy="low", contextual_notes="Use the existing local test runner and fixtures. Three total tests, no new app or tools."), None),
        ("G", CheckInStart(mode="start", goal="Draft a one-page explanation of SQLite transactions using only local notes",
                           available_minutes=15, energy="low", contextual_notes="Existing local text editor and notes; no internet or new downloads."), None),
    ])
    if hotfix_cases:
        result.extend([
            ("I", CheckInStart(mode="start", goal="i want to make a dish but im tired", available_minutes=10, energy="low"),
             "Make a no-cook sandwich using sliced bread, cheese and washed lettuce that I already have."),
            ("J", CheckInStart(mode="start", goal="Study Python list comprehensions using my three existing example lists", available_minutes=15, energy="low"), None),
            ("K", CheckInStart(mode="start", goal="Make a no-cook vegetarian snack using only bread, tomato and cheese; no stove and no shopping", available_minutes=10, energy="low"), None),
            ("L", CheckInStart(mode="start", goal="Tidy the items on my desk using the storage already beside it", available_minutes=5, energy="low"), None),
        ])
    return result


def reliability_cases() -> list[tuple[str, CheckInStart, str | None]]:
    # Fictional QA answers only, never production defaults or invented user facts.
    return [(case, CheckInStart(mode="start", goal=goal, available_minutes=minutes, energy=energy), answer) for case, goal, minutes, energy, answer in [
        ("A", "Prepare a 5-minute introduction to artificial intelligence for my classmates. Research the basics, create three slides, and practice.", 60, "medium", None),
        ("B", "I want to make something simple to eat, but I'm tired.", 10, "low", "Use sliced bread, tomato and cheese I already have to make a no-cook sandwich."),
        ("C", "Study Python loops for tomorrow's quiz.", 30, "medium", None),
        ("D", "Clean my desk before studying.", 15, "low", None),
        ("E", "Prepare a short presentation with exactly three slides and one timed rehearsal.", 45, "medium", "Introduce artificial intelligence to my classmates using locally available materials."),
        ("F", "I need to present a complex topic that I know nothing about.", 60, "low", None),
        ("G", "Write three unit tests for my FastAPI login endpoint using the existing local test runner and fixtures.", 30, "medium", None),
    ]]


def sizing_cases() -> list[tuple[str, CheckInStart, str | None]]:
    return [
        ("A", CheckInStart(mode="start", goal="Make a no-cook sandwich using only bread, tomato and cheese already available; no stove and no shopping.", available_minutes=10, energy="low"), None),
        ("B", CheckInStart(mode="start", goal="Create a local study guide for Python loops: explain for and while loops, write and run three examples, draw a flowchart, and finish with a self-check quiz and answer key using my existing notes and Python editor.", available_minutes=20, energy="medium"), None),
    ]


def qa_cases() -> list[tuple[str, CheckInStart, str | None]]:
    """Four fictional release-QA inputs; one operation each, no automatic replan."""
    return [
        ("A", CheckInStart(mode="start", goal="Clean my desk before studying.", available_minutes=15, energy="low"), None),
        ("B", CheckInStart(mode="start", goal="Study Python loops for tomorrow's quiz.", available_minutes=30, energy="medium"), None),
        ("C", sizing_cases()[1][1], None),
        ("D", CheckInStart(mode="start", goal="Make a no-cook vegetarian snack using only bread, tomato and cheese; no stove and no shopping", available_minutes=10, energy="low"), None),
    ]


def metrics(row: dict, generation, review=None, failure=None) -> None:
    attempts = generation.attempts if generation else getattr(failure, "attempts", ())
    row.update(structural_validity=any(a.validation_success is True for a in attempts), attempts=[asdict(a) for a in attempts],
               first_attempt_structural_success=attempts[0].validation_success if attempts else None,
               retry_count=max(0, len(attempts) - 1),
               review=review.model_dump() if review else None,
               generated_plan=generation.plan.model_dump() if generation else None,
               quest_count=len(generation.plan.quests) if generation else None,
               candidates=[{"plan": a.plan.model_dump(), "codes": list(a.codes), "stage": a.stage,
                            "review": a.review.model_dump() if a.review else None, "warnings": list(a.warnings),
                            "repair_targets": [asdict(target) for target in a.repair_targets]} for a in getattr(generation, "assessments", ())],
               human_quality_review={"acceptable": None, "unsupported_assumptions": None, "notes": None,
                                     "reviewer": None})


async def benchmark(args) -> dict:
    reference = args.reference_time or datetime.now().astimezone()
    require_local_url(args.url)
    report = {"benchmark_version": 1, "quality_version": QUALITY_VERSION, "prompt_version": PROMPT_VERSION,
              "machine_label": args.machine_label, "checkpoint": command_output(["git", "rev-parse", "HEAD"]),
              "started_at": datetime.now().astimezone().isoformat(), "reference_time": reference.isoformat(),
              "hardware": hardware_info(), "model": args.model, "url": args.url,
              "settings": {**GENERATION_OPTIONS, "think": False if args.model.startswith("qwen3:") else None,
                           "pipeline_seconds": 120, "generation_seconds": 120, "attempt_seconds": 60,
                           "max_proposal_attempts": 2, "max_review_calls": 0, "shared_format_constraint_retry": True,
                           "subjective_findings_blocking": False},
              "internet_disconnected": False, "fictional_inputs_only": True, "selected_initial_cases": args.case, "rows": []}
    native_outputs = []
    async def capture_native(response):
        if args.capture_native and response.request.url.path == "/api/generate":
            await response.aread()
            try:
                payload = json.loads(response.request.content)
                data = response.json()
                native_outputs.append({"schema_kind": "repair" if "repairs" in payload.get("format", {}).get("properties", {}) else "review" if "acceptable" in payload.get("format", {}).get("properties", {}) or "anyOf" in payload.get("format", {}) else "proposal",
                    "status": response.status_code, "response": data.get("response"), "done": data.get("done"), "done_reason": data.get("done_reason"), "error": data.get("error")})
            except (ValueError, AttributeError):
                native_outputs.append({"status": response.status_code, "error": "non-JSON envelope"})
    async with httpx.AsyncClient(base_url=args.url, trust_env=False, timeout=5, event_hooks={"response": [capture_native]}) as client:
        adapter = OllamaClient(client, Settings(_env_file=None, ollama_model=args.model))
        status = await adapter.status()
        report["discovery"] = status.model_dump()
        if not status.available:
            report["status"] = "untested"
            return report
        report["runtime"] = (await client.get("/api/version")).json()
        report["installed"] = (await client.get("/api/tags")).json()
        report["resident_before"] = (await client.get("/api/ps")).json()
        with tempfile.TemporaryDirectory(prefix="quest-pipeline-benchmark-") as directory:
            database = create_sqlite_engine(f"sqlite:///{Path(directory) / 'fictional.db'}")
            try:
                initialize_database(database)
                quests = QuestService(database)
                service = CheckInService(quests)
                saved_specific = None
                for case, context, fictional_answer in (qa_cases() if args.qa_cases else sizing_cases() if args.sizing_cases else reliability_cases() if args.reliability_cases else fictional_cases(reference, args.hotfix_cases)):
                    if args.case and case not in args.case:
                        continue
                    native_outputs.clear()
                    start = perf_counter()
                    check_in, _ = service.submit(context, str(uuid4()))
                    question = check_in.question
                    if question and fictional_answer:
                        check_in, _ = service.submit(CheckInAnswer(mode="answer", check_in_id=check_in.id,
                                        expected_revision=check_in.revision, answer=fictional_answer), str(uuid4()))
                    row = {"case": case, "input": context.model_dump(mode="json"), "clarification_question": question,
                           "fictional_clarification_answer": fictional_answer if question else None, "check_in_status": check_in.status, "effective_context": check_in.context.model_dump(mode="json"), "inference_attempted": check_in.status == "ready"}
                    if check_in.status == "needs_follow_up":
                        metrics(row, None)
                        row.update(pipeline_accepted=False, error_code=None, awaiting_clarification=True, end_to_end_seconds=perf_counter() - start)
                        report["rows"].append(row)
                        print(f"{case}: CLARIFICATION_REQUIRED (no inference)", flush=True)
                        if args.output:
                            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        continue
                    try:
                        result = await service.generate(GenerateQuestlineRequest(check_in_id=check_in.id,
                                                        expected_check_in_revision=check_in.revision), str(uuid4()), adapter)
                        metrics(row, result.generation, result.review)
                        row.update(pipeline_accepted=True, error_code=None, public_view=result.view.model_dump(mode="json"),
                                   pipeline_latency_seconds=result.latency_seconds)
                        if saved_specific is None or case == "F":
                            saved_specific = result.view
                    except QuestError as error:
                        metrics(row, getattr(error, "generation_result", None), getattr(error, "review_result", None),
                                getattr(error, "generation_error", None))
                        row.update(pipeline_accepted=False, error_code=error.code, error_details=error.details)
                    row["end_to_end_seconds"] = perf_counter() - start
                    if args.capture_native:
                        row["native_outputs"] = list(native_outputs)
                    report["rows"].append(row)
                    print(f"{case}: {'SAVED' if row['pipeline_accepted'] else row['error_code']} "
                          f"structural={row['structural_validity']} retry={row['retry_count']} "
                          f"clarified={question is not None} {row['end_to_end_seconds']:.2f}s", flush=True)
                    if args.output:
                        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                if saved_specific and not args.case and not args.reliability_cases and not args.sizing_cases and not args.qa_cases:
                    # Synthetic explicit completion exercises the real state engine,
                    # not a claim that somebody performed the task or criteria.
                    completed = quests.complete_quest(saved_specific.current_quest.id, saved_specific.revision)
                    history = [q.model_dump(mode="json") for q in completed.questline.completed_quests]
                    profile = quests.get_profile().model_dump()
                    row = {"case": "H", "source_goal": saved_specific.goal,
                           "synthetic_explicit_completion": True, "profile_before": profile}
                    start = perf_counter()
                    try:
                        result = await service.generate(ReplanRequest(expected_revision=completed.questline.revision,
                                        available_minutes=15, energy="low", reason="Only a short local work session remains."),
                                        str(uuid4()), adapter, line_id=saved_specific.id)
                        metrics(row, result.generation, result.review)
                        row.update(pipeline_accepted=True, error_code=None, public_view=result.view.model_dump(mode="json"))
                        row["history_preserved"] = [q.model_dump(mode="json") for q in result.view.completed_quests] == history
                    except QuestError as error:
                        metrics(row, getattr(error, "generation_result", None), getattr(error, "review_result", None),
                                getattr(error, "generation_error", None))
                        row.update(pipeline_accepted=False, error_code=error.code, error_details=error.details)
                        row["history_preserved"] = [q.model_dump(mode="json") for q in quests.get_questline(saved_specific.id).completed_quests] == history
                    row["xp_preserved"] = quests.get_profile().model_dump() == profile
                    row["end_to_end_seconds"] = perf_counter() - start
                    report["rows"].append(row)
                    print(f"H replan: {'SAVED' if row['pipeline_accepted'] else row['error_code']} {row['end_to_end_seconds']:.2f}s", flush=True)
                else:
                    report["replan_status"] = "not requested: targeted/count/QA cases" if args.case or args.reliability_cases or args.sizing_cases or args.qa_cases else "untested: no initial scenario was saved"
            finally:
                database.dispose()
    rows = report["rows"]
    latencies = [r["end_to_end_seconds"] for r in rows if r.get("inference_attempted", True)]
    report["summary"] = {"runs": len(rows), "generation_operations": len(latencies), "awaiting_clarification": sum(r.get("awaiting_clarification", False) for r in rows), "structurally_valid_plans": sum(r["structural_validity"] for r in rows),
        "pipeline_accepted": sum(r["pipeline_accepted"] for r in rows),
        "first_attempt_structural_successes": sum(r["first_attempt_structural_success"] is True for r in rows),
        "operations_with_retry": sum(r["retry_count"] > 0 for r in rows),
        "timeouts": sum(r["error_code"] == "AI_TIMEOUT" for r in rows),
        "average_end_to_end_seconds": statistics.mean(latencies) if latencies else None,
        "median_end_to_end_seconds": statistics.median(latencies) if latencies else None, "max_end_to_end_seconds": max(latencies, default=None)}
    report["status"] = "measured; independent semantic review pending"
    return report


def main() -> int:
    settings = Settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-native", action="store_true", help="Developer-only local native responses for these hardcoded fictional scenarios; never production logs.")
    parser.add_argument("--reliability-cases", action="store_true", help="Phase 3C exact A–F plus an additional existing-runner test case; unresolved topics never receive invented answers.")
    parser.add_argument("--sizing-cases", action="store_true", help="Two fictional complete-goal cases: simple sandwich and complex multi-deliverable study guide.")
    parser.add_argument("--qa-cases", action="store_true", help="Phase 5A household, study, complex guide and short low-energy snack; four operations, no replan.")
    parser.add_argument("--case", action="append", choices=list("ABCDEFGIJKL"), help="Limit to selected initial cases; repeat to select several. No replan in a targeted run.")
    parser.add_argument("--hotfix-cases", action="store_true", help="Add fictional cooking, study, constrained snack and household cases to A–H.")
    parser.add_argument("--model", default=settings.ollama_model)
    parser.add_argument("--url", default=str(settings.ollama_base_url).rstrip("/"))
    parser.add_argument("--reference-time", type=reference_time)
    parser.add_argument("--machine-label", default="Development machine (not Windows demo verification)")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.qa_cases and (args.sizing_cases or args.reliability_cases or args.hotfix_cases):
        parser.error("Choose QA cases separately from other cohorts.")
    if args.sizing_cases and (args.reliability_cases or args.hotfix_cases):
        parser.error("Choose sizing cases separately from other cohorts.")
    try:
        require_local_url(args.url)
    except ValueError as exc:
        parser.error(str(exc))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write("{}\n")
        except FileExistsError:
            parser.error("Output already exists; choose a new filename.")
    report = asyncio.run(benchmark(args))
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report.get("summary", report.get("discovery")), indent=2))
    return 1 if report["status"] == "untested" else 0


if __name__ == "__main__":
    raise SystemExit(main())
