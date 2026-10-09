"""Development-only browser fixture: real API/SQLite, fictional mocked Ollama.

Never imported by the application. DATABASE_URL must point to the harness temp DB.
"""
import asyncio
import json
import os
from pathlib import Path

import httpx
from fastapi import Request

from app.main import app
from app.ollama import OllamaClient
from app.routes import get_ollama
from app.config import get_settings
from app.encouragement import TAILS


def mode():
    return Path(os.environ["QUEST_TEST_MODE_FILE"]).read_text().strip()


async def response(request):
    current = mode()
    if current == "unavailable":
        raise httpx.ConnectError("Fictional unavailable runtime", request=request)
    if current == "timeout":
        raise httpx.ReadTimeout("Fictional timeout", request=request)
    if request.url.path == "/api/tags":
        return httpx.Response(200, json={"models": [{"name": "qwen3:1.7b"}]})
    if current == "slow":
        await asyncio.sleep(0.5)
    payload = json.loads(request.content)
    if current == "invalid":
        output = "not JSON"
    elif "acceptable" in payload.get("format", {}).get("properties", {}) or any("acceptable" in branch.get("properties", {}) for branch in payload.get("format", {}).get("anyOf", [])):
        output = json.dumps({"acceptable": current != "rejected", "confidence": "high", "issues": [] if current != "rejected" else ["unsupported_assumption"]})
    else:
        plan = {"quests": [
            {"title": "Inspect the endpoint", "action": "Read the local FastAPI login endpoint and list three expected responses.",
             "completion_criteria": "A written list contains the three expected responses.", "estimated_minutes": 5, "difficulty": "easy"},
            {"title": "Write the tests", "action": "Write three unit tests for the FastAPI login endpoint using the existing local test suite.",
             "completion_criteria": "The test file contains three tests with assertions for the listed responses.", "estimated_minutes": 30, "difficulty": "medium"},
            {"title": "Run the tests", "action": "Run the three tests locally and record each result.",
             "completion_criteria": "The saved result lists each test and its pass or fail outcome.", "estimated_minutes": 10, "difficulty": "easy"},
        ]}
        # Two model-copy examples and a missing-copy legacy/fallback stage.
        for index, quest in enumerate(plan["quests"][:2]):
            quest["completion_encouragement"] = f'You completed "{quest["title"]}". {TAILS[index + 1]}'
        if current == "rejected":
            # Actual essential violation; subjective self-review is no longer
            # part of production acceptance.
            plan["quests"][0]["action"] = "Create an online account and download a required test runner."
        if current in {"stages-2", "stages-6"}:
            count = int(current[-1])
            plan["quests"] = [{"title": f"Sized stage {index + 1}",
                "action": f"Record local test artifact {index + 1}. Check it against the supplied goal.",
                "completion_criteria": f"Artifact {index + 1} is written and checked.",
                "estimated_minutes": 5, "difficulty": "easy"} for index in range(count)]
            # The explicit three-test goal is still satisfied within the chosen
            # count; these are labeled synthetic fixtures, not live AI evidence.
            plan["quests"][0]["action"] = "Write three unit tests for the local FastAPI login endpoint. Record test artifact 1."
        if current == "qa-household":
            plan["quests"] = [
                {"title": "Clear the desk", "action": "Move items off the desk into the storage already beside it.", "completion_criteria": "The desk surface has no loose items.", "estimated_minutes": 5, "difficulty": "easy"},
                {"title": "Set up the study space", "action": "Place the existing study notes on the clear desk.", "completion_criteria": "The notes are on the desk and the working area is clear.", "estimated_minutes": 3, "difficulty": "easy"},
            ]
        if current == "qa-presentation":
            plan["quests"] = [
                {"title": "Draft the AI introduction", "action": "Use the existing local notes to create exactly three slides introducing artificial intelligence to classmates: definition, an example, and limitations.", "completion_criteria": "Three slides contain the definition, example and limitations of artificial intelligence.", "estimated_minutes": 10, "difficulty": "easy"},
                {"title": "Rehearse the introduction", "action": "Give one timed five-minute spoken rehearsal using the three slides and record its duration.", "completion_criteria": "One spoken rehearsal has a recorded five-minute duration.", "estimated_minutes": 5, "difficulty": "easy"},
            ]
        if current in {"qa-study", "qa-replan"}:
            entries = [
                ("Read the loop notes", "Read the existing Python notes and write the difference between for and while loops.", "A written sentence compares for and while loops.", "easy"),
                ("Run a for loop", "Run a Python for loop over three existing values and record its output.", "The output lists all three values.", "easy"),
                ("Run a while loop", "Run a Python while loop with a stopping condition and record the output.", "The output and stopping condition are recorded.", "easy"),
                ("Compare the loop results", "Compare the recorded for and while loop outputs in two sentences.", "Two sentences compare the recorded outputs.", "medium"),
                ("Check a boundary case", "Run the Python loops with an empty list or a false initial condition and record the result.", "Each boundary-case result is recorded.", "medium"),
                ("Test the loop knowledge", "Write two questions about Python loops and answer them using the recorded examples.", "Two questions and their answers are written.", "easy"),
            ]
            if current == "qa-replan":
                entries = [("Replanned " + title, action, criteria, difficulty) for title, action, criteria, difficulty in entries[1:]]
            plan["quests"] = [{"title": title, "action": action, "completion_criteria": criteria, "estimated_minutes": 5, "difficulty": difficulty} for title, action, criteria, difficulty in entries]
        output = json.dumps(plan)
    return httpx.Response(200, json={"response": output, "done": True, "done_reason": "stop"})


client = httpx.AsyncClient(base_url="http://127.0.0.1:11434", transport=httpx.MockTransport(response))
fixture = OllamaClient(client, get_settings())
def selected_ollama(request: Request):
    return request.app.state.ollama if mode() == "real" else fixture


app.dependency_overrides[get_ollama] = selected_ollama
