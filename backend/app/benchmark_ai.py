"""Development-only, fictional-input benchmark: python -m app.benchmark_ai."""

import argparse
import asyncio
import json
import math
import platform
import shutil
import statistics
import subprocess
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from importlib.metadata import version
from pathlib import Path

import httpx

from .config import Settings
from .ollama import (
    GENERATION_OPTIONS, PROMPT_VERSION, QUEST_SYSTEM, OllamaClient,
    QuestGenerationError, require_local_url,
)
from .schemas import CheckInInput, QuestPlan


def command_output(command: list[str]) -> str | None:
    if not shutil.which(command[0]):
        return None
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def hardware_info() -> dict:
    cpu = platform.processor() or None
    ram = None
    gpu = None
    available_ram = None
    if platform.system() == "Linux":
        cpuinfo = Path("/proc/cpuinfo").read_text()
        cpu = next((line.split(":", 1)[1].strip() for line in cpuinfo.splitlines() if line.startswith("model name")), cpu)
        memory = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines()}
        ram, available_ram = memory.get("MemTotal"), memory.get("MemAvailable")
        pci = command_output(["lspci"])
        gpu = [line for line in (pci or "").splitlines() if any(term in line.lower() for term in ("vga", "3d controller", "display controller"))] or None
    elif platform.system() == "Windows":
        cpu = command_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"]) or cpu
        memory = command_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        ram = int(memory) if memory and memory.isdigit() else None
        gpu = command_output(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"])
    return {"os": platform.system(), "os_release": platform.release(), "architecture": platform.machine(),
            "cpu": cpu, "ram_bytes": ram, "available_ram_bytes_at_start": available_ram, "gpu_detected": gpu,
            "nvidia_gpu_memory": command_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]),
            "python": platform.python_version(), "packages": {name: version(name) for name in ("pydantic", "httpx")}}


def scenarios(reference: datetime) -> list[tuple[str, CheckInInput]]:
    tonight = reference.replace(hour=23, minute=59, second=0, microsecond=0)
    cases = [
        ("A", "Finish a programming assignment", 20, "low", tonight + timedelta(days=1)),
        ("B", "Prepare for an Algorithms and Complexity exam", 60, "medium", tonight + timedelta(days=3)),
        ("C", "Improve my programming skills", 30, "medium", None),
        ("D", "Prepare a project presentation", 15, "low", tonight),
        ("E", "Build a basic CRUD web application", 90, "high", tonight + timedelta(days=7)),
    ]
    return [(key, CheckInInput(goal=goal, available_minutes=minutes, energy=energy, deadline=deadline))
            for key, goal, minutes, energy, deadline in cases]


def summarize(rows: list[dict]) -> dict:
    attempts = [attempt for row in rows for attempt in row["attempts"]]
    latencies = [row["latency_seconds"] for row in rows]
    valid = sum(attempt["validation_success"] is True for attempt in attempts)
    successes = sum(row["validation_success"] for row in rows)
    return {"scenario_runs": len(rows), "successful_plans": successes,
            "first_attempt_successes": sum(row["validation_success"] and row["retry_count"] == 0 for row in rows),
            "successes_after_retry": sum(row["validation_success"] and row["retry_count"] == 1 for row in rows),
            "inference_attempts": len(attempts), "schema_valid_attempts": valid,
            "schema_evaluated_attempts": sum(attempt["validation_success"] is not None for attempt in attempts),
            "schema_validity_rate": valid / len(attempts) if attempts else None,
            "plan_success_rate": successes / len(rows) if rows else None,
            "median_latency_seconds": statistics.median(latencies) if latencies else None,
            "maximum_latency_seconds": max(latencies) if latencies else None}


async def benchmark(args: argparse.Namespace) -> dict:
    reference = args.reference_time or datetime.now(timezone.utc).astimezone()
    report = {"benchmark_version": 1, "machine_label": args.machine_label or f"{platform.system()} development machine",
              "started_at": datetime.now(timezone.utc).isoformat(), "reference_time": reference.isoformat(),
              "checkpoint": command_output(["git", "rev-parse", "HEAD"]), "hardware": hardware_info(),
              "model": args.model, "ollama_url": args.url, "timeout_seconds": args.timeout,
              "attempt_timeout_seconds": args.attempt_timeout, "connect_timeout_seconds": 3,
              "prompt_version": PROMPT_VERSION, "system_instruction": QUEST_SYSTEM,
              "schema": QuestPlan.model_json_schema(), "options": GENERATION_OPTIONS,
              "think": False if args.model.startswith("qwen3:") else "omitted",
              "status": "untested", "results": [], "summary": summarize([])}
    async with httpx.AsyncClient(base_url=args.url, trust_env=False, timeout=httpx.Timeout(5, connect=3)) as client:
        try:
            tags = await client.get("/api/tags"); tags.raise_for_status()
            tag_data = tags.json()
            models = tag_data.get("models")
            if not isinstance(models, list) or any(not isinstance(model, dict) for model in models):
                raise ValueError("Invalid model list")
            report["installed_models"] = [{key: model.get(key) for key in ("name", "digest", "size", "details")} for model in models]
            normalized = args.model if ":" in args.model else args.model + ":latest"
            if not any(model.get("name") == normalized or model.get("model") == normalized for model in models):
                report["unavailable_reason"] = "Configured model not installed; no download attempted."
                return report
            runtime = await client.get("/api/version"); runtime.raise_for_status()
            report["ollama_version"] = runtime.json().get("version")
        except (httpx.HTTPError, ValueError, AttributeError):
            report["unavailable_reason"] = "Local runtime discovery failed; verify Ollama URL/runtime."
            return report
        try:
            placement = await client.get("/api/ps"); placement.raise_for_status()
            report["loaded_models_before"] = [{key: model.get(key) for key in ("name", "size", "size_vram", "context_length")}
                                              for model in placement.json().get("models", [])]
        except (httpx.HTTPError, ValueError, AttributeError, TypeError):
            report["loaded_models_before"] = None
        adapter = OllamaClient(client, Settings(ollama_model=args.model, ollama_base_url=args.url))
        for repeat in range(1, args.repeats + 1):
            for name, check_in in scenarios(reference):
                row = {"scenario": name, "repeat": repeat, "model": args.model,
                       "check_in": check_in.model_dump(mode="json"), "validation_success": False,
                       "quest_count": None, "error_category": None, "plan": None,
                       "first_estimate_within_session": None,
                       "quality_review": {"first_quest_startable": None, "observable_criteria": None,
                                          "capacity_aware": None, "clarification_needed": None,
                                          "notes": "Manual content review required; schema validity is not quality."}}
                print(f"{args.model} scenario {name} run {repeat}: generating…", flush=True)
                try:
                    result = await adapter.generate_quest_plan(check_in, timeout=args.timeout,
                                                               attempt_timeout=args.attempt_timeout, reference_time=reference)
                    row.update(validation_success=True, quest_count=len(result.plan.quests), plan=result.plan.model_dump(mode="json"),
                               first_estimate_within_session=result.plan.quests[0].estimated_minutes <= check_in.available_minutes)
                    attempts, latency = result.attempts, result.latency_seconds
                except QuestGenerationError as exc:
                    row["error_category"] = exc.code
                    attempts, latency = exc.attempts, exc.latency_seconds
                row.update(attempts=[asdict(attempt) for attempt in attempts], retry_count=max(0, len(attempts) - 1),
                           latency_seconds=latency)
                # Runtime placement is observed after inference, not an asserted GPU/RAM peak.
                try:
                    placement = await client.get("/api/ps"); placement.raise_for_status()
                    row["loaded_models_after"] = [{key: model.get(key) for key in ("name", "size", "size_vram", "context_length")}
                                                  for model in placement.json().get("models", [])]
                except (httpx.HTTPError, ValueError, AttributeError, TypeError):
                    row["loaded_models_after"] = None
                report["results"].append(row)
                print(f"  {'VALID' if row['validation_success'] else row['error_category']} | "
                      f"{latency:.2f}s | retries={row['retry_count']} | quests={row['quest_count']}", flush=True)
                if row["plan"]:
                    for quest in row["plan"]["quests"]:
                        print(f"  - {quest['title']} ({quest['estimated_minutes']}m, {quest['difficulty']}): {quest['action']}\n"
                              f"    Done: {quest['completion_criteria']}", flush=True)
        report.update(status="completed", summary=summarize(report["results"]), finished_at=datetime.now(timezone.utc).isoformat())
        return report


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Use finite positive seconds.")
    return number


def reference_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("Use an offset-bearing ISO timestamp.") from None


def main() -> int:
    settings = Settings()
    parser = argparse.ArgumentParser(description="Fictional A–E local quest-plan benchmark; no DB writes or model pulls.")
    parser.add_argument("--model", default=settings.ollama_model)
    parser.add_argument("--url", default=str(settings.ollama_base_url).rstrip("/"))
    parser.add_argument("--timeout", type=positive_seconds, default=120, help="Whole operation including at most one format retry.")
    parser.add_argument("--attempt-timeout", type=positive_seconds, default=60)
    parser.add_argument("--repeats", type=int, default=1, help="Runs of all five scenarios (default 1).")
    parser.add_argument("--reference-time", type=reference_time, help="Fix fictional deadline reference for reproduction.")
    parser.add_argument("--machine-label")
    parser.add_argument("--output", type=Path, help="Optional JSON file; refuses to overwrite an existing file.")
    args = parser.parse_args()
    try:
        require_local_url(args.url)
    except (ValueError, httpx.InvalidURL):
        parser.error("--url must identify a loopback Ollama server without credentials/query/fragment.")
    if not args.model.strip() or args.repeats < 1:
        parser.error("Use a nonblank model and at least one repeat.")
    if args.output and args.output.exists():
        parser.error("Output already exists; choose a new results filename.")
    report = asyncio.run(benchmark(args))
    print(json.dumps({"status": report["status"], "summary": report["summary"],
                      "unavailable_reason": report.get("unavailable_reason")}, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, ensure_ascii=False)
        print(f"Wrote results: {args.output}")
    return 0 if report["status"] == "completed" and report["summary"]["plan_success_rate"] == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
