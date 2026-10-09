# Structured local AI benchmark — Phase 1B

October 9, 2026; **Matthew's Linux development machine**, checkpoint `56c3c1a`
plus the uncommitted Phase 1B changes. **Status: PARTIAL.** Strict local generation,
bounded recovery and repeatable benchmarking work. Goal alignment, clarification
and offline-appropriate quest content are not reliable enough for the P0 AI gate.
Windows demo-laptop performance and actual disconnected-internet inference are
NOT TESTED here. No frontend, persistence, XP or production quest API was added.

## 1. Objective and methodology

Test initial 3–5-quest proposals using [app.benchmark_ai](../backend/app/benchmark_ai.py)
and the reusable [OllamaClient.generate_quest_plan](../backend/app/ollama.py).
The CLI imports no database module and never pulls models. Its only inputs are
five hardcoded fictional scenarios:

| Case | Goal | Session / energy | Fictional deadline | Expected quality |
| --- | --- | --- | --- | --- |
| A | Finish a programming assignment | 20 minutes / low | Tomorrow | Small requirements-based first action, no invented assignment |
| B | Prepare for an Algorithms and Complexity exam | 60 / medium | Three days | Concrete study and observable evidence |
| C | Improve my programming skills | 30 / medium | None | Select a focus or identify clarification; no assumed language |
| D | Prepare a project presentation | 15 / low | Tonight | Minimal useful presentation artifact first |
| E | Build a basic CRUD web application | 90 / high | One week | Sensible implementation dependencies and realistic first action |

All sweeps used reference time `2026-10-09T21:00:00+08:00`. Python computes
deadlines at 23:59 on the corresponding local date; v2/v3 also pass Python-computed
minutes remaining. This fixed fictional reference is separate from actual
execution timestamps in the JSON artifacts. Session capacity applies to the
first quest, not the sum of all estimates. No user task was actually completed.

Sequence: one A–E sweep per model with v1; two per model with v2; three diagnostic
case-C calls; two per model with final v3. **50 scenario runs and 3 diagnostic calls**
were executed, with every earlier failure retained. Prompt revisions/hardware
placement differ; do not pool those cohorts to claim final-setting reliability.
Repeats use seed 42, so they are limited consistency/latency samples, not independent
random trials or proof of general reliability.

Latency is monotonic wall time for the generation operation, including inference,
validation and any correction retry. It excludes CLI hardware/discovery queries
and the post-operation `/api/ps` snapshot. Median/max include all runs in that
cohort, including failures. A valid attempt must pass strict schema **and** domain
checks; final accepted-plan success is reported separately. Timeouts have no
schema-evaluable response and must not be described as malformed JSON.

## 2. Hardware, runtime and artifacts

| Item | Actual observation |
| --- | --- |
| OS | Linux x86_64, kernel `7.2.5-3-omarchy` |
| CPU | AMD A10-7860K Radeon R7, 4 CPU cores (`lscpu`); model name also reports 4C+8G compute cores |
| RAM | 15,640,678,400 bytes reported by Linux, about 14.57 GiB; available RAM varied by sweep |
| Detected GPUs | AMD Kaveri/Radeon R7; NVIDIA GeForce GTX 1050 Ti |
| NVIDIA memory | 4096 MiB reported by `nvidia-smi` |
| Python / validation / HTTP | Python 3.14.7; Pydantic 2.14.0; HTTPX 0.28.1 |
| Ollama | 0.40.2 at `http://127.0.0.1:11434` |
| Primary | `qwen3:1.7b`, digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`, Q4_K_M |
| Backup | `qwen2.5:1.5b`, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`, Q4_K_M |

The primary tag is preserved as locked. Its installed runtime metadata reports
`parameter_size: 2.0B`; this is recorded rather than silently relabeled. Verify
the exact artifact/model card and licensing before submission. No weights were
downloaded, replaced or removed. RAM peak, full cold OS/disk-cache behavior and
Ollama daemon startup latency were not measured.

Initial backup runs had only 306,530,221 bytes in VRAM out of a reported resident
size of 1,380,985,075; the primary also remained resident during A–D. All five
backup operations timed out. This is a confounded placement result, not proof
the backup cannot generate valid plans. After explicitly unloading benchmark
models from RAM, solo backup runs reported size_vram equal to resident size
(1,166,236,712 bytes); primary solo runs likewise reported full placement
(1,702,593,821 bytes). Placement changes are a plausible contributor, not a
controlled proof of causality: the prompt also changed.

Final v3 reports show an empty resident-model list before each sweep. The first
primary call reported 4.53 seconds model load (13.29 seconds end-to-end); the first
backup call reported 4.19 seconds load (11.47 seconds end-to-end). Later calls
were warm. These are runtime-reported model loads, not process cold-start or
peak-memory measurements. Do not extrapolate these results to James's laptop.

## 3. Executable commands

Use the existing backend virtual environment; no extra dependencies are needed.
Ollama must already be running and both tags installed (`ollama list`). To keep
the comparison to one resident model, explicitly unload the previous benchmark
model between sweeps. `ollama stop` unloads RAM, not installed weights; use it only
on a model whose current work may safely stop. No automatic switching/unloading
is built into the module or CLI.

Actual final Linux commands, from `backend/` (output filenames must be new):

```bash
ollama stop qwen3:1.7b
.venv/bin/python -m app.benchmark_ai --model qwen3:1.7b --url http://127.0.0.1:11434 --timeout 120 --attempt-timeout 60 --repeats 2 --reference-time 2026-10-09T21:00:00+08:00 --machine-label 'Matthew Linux development machine' --output ../docs/benchmarks/linux-qwen3-v3.json
ollama stop qwen3:1.7b
.venv/bin/python -m app.benchmark_ai --model qwen2.5:1.5b --url http://127.0.0.1:11434 --timeout 120 --attempt-timeout 60 --repeats 2 --reference-time 2026-10-09T21:00:00+08:00 --machine-label 'Matthew Linux development machine' --output ../docs/benchmarks/linux-qwen25-v3.json
ollama stop qwen2.5:1.5b
```

The initial run additionally stopped both tags before the solo backup comparison.
The default CLI runs A–E once; `--repeats 2` runs them twice, sequentially. Without
`--output` it prints results only. `--model`/`--url` override the existing
OLLAMA_MODEL/OLLAMA_BASE_URL settings for that process only. URLs must be loopback;
proxy environment variables are ignored. An absent model/runtime yields UNTESTED
discovery status and exit 1, no pull. Exit 0 means every plan validated within
budget, **not** that semantic quality passed. Existing output files are refused.

## 4. Prompt, schema and model settings

Final prompt version `initial-quests-v3`: system instructions plus explicit
plain-language task/session context, a JSON-quoted goal, typed deadline and
Python-computed remaining time, and the Pydantic JSON schema in the prompt.
Responsibilities: real deliverable contributions, one bounded action per quest,
observable criteria, small low-energy first step, no invented circumstances,
no mandatory online resources, no clinical treatment, and no authority fields.
This is instruction intent, not proof of compliance.

POST local Ollama `/api/generate`: `stream=false`, `format=QuestPlan.model_json_schema()`,
`system`, `prompt`, `options={temperature:0,seed:42,num_predict:1600,num_ctx:4096}`.
Qwen3 additionally receives `think:false`; accepted Qwen3 attempt metadata contained
no thinking text. The flag is omitted for Qwen2.5. The native schema request is
supported by this installed runtime, and matches the
[Ollama generate API](https://docs.ollama.com/api/generate) and
[structured-output guidance](https://docs.ollama.com/capabilities/structured-outputs).

Reuse `/api/generate` because existing transport and metadata work. A one-case
`/api/chat` probe with system/user messages also returned valid JSON but still
invented Python. Inline instructions did not solve that either. A one-case
plain-language context probe avoided choosing a language; the complete v3 sweep
still failed that expectation on C. Do not generalize a favorable single probe.
No chat orchestration/framework or new public endpoint was introduced.

Strict Pydantic models in [schemas.py](../backend/app/schemas.py):

- CheckInInput: trimmed goal 1–4000 chars, strict available_minutes 1–1440,
  energy low/medium/high, optional offset-bearing deadline normalized to UTC.
  This is the Phase 1B subset; ready interpretation, notes and follow-up state
  remain Phase 3 work, not silently implemented here.
- QuestProposal: bounded nonblank title/action/criteria (100/2000/1000 chars),
  strict estimated_minutes 1–1440, difficulty easy/medium/hard, optional null or
  nonblank hint up to 1000 chars.
- QuestPlan: 3–5 proposals, distinct normalized titles/actions and first estimate
  <= supplied session capacity. Extra fields forbidden at every model boundary;
  numeric coercions/booleans as integers rejected. IDs/XP/state/revisions/profile
  fields are not part of this content schema.

No all-quests-fit-session constraint or automatic difficulty/estimate rewriting.
No code-fence stripping, JSON repair, fabricated fallback content, saving or rewards.
Specificity, goal alignment and actual effort are not proven by these validators.

## 5. Actual validation and latency statistics

### Final v3, solo resident model, two A–E sweeps each

| Model | Accepted plans | First-attempt success | Success after retry | Valid proposal attempts / all inference attempts | Median | Maximum |
| --- | --- | --- | --- | --- | --- | --- |
| qwen3:1.7b | 10/10 | 10/10 | 0/10 | 10/10 (100%) | 8.60 s | 13.29 s |
| qwen2.5:1.5b | 10/10 | 9/10 | 1/10 | 10/11 (90.9%) | 8.00 s | 14.76 s |

The backup's B/run-1 first estimate exceeded session capacity; its one correction
validated. No final timeout, malformed JSON or terminal error occurred. All accepted
first estimates meet capacity because the backend rejects violations, not because
every initial model proposal obeys instructions.

| Model / case | Run 1 seconds / quests / retries | Run 2 seconds / quests / retries | Accepted / terminal error |
| --- | --- | --- | --- |
| qwen3 A | 13.29 / 3 / 0 | 7.72 / 3 / 0 | Both valid / none |
| qwen3 B | 8.47 / 3 / 0 | 8.54 / 3 / 0 | Both valid / none |
| qwen3 C | 8.66 / 3 / 0 | 8.65 / 3 / 0 | Both valid / none |
| qwen3 D | 7.48 / 3 / 0 | 6.85 / 3 / 0 | Both valid / none |
| qwen3 E | 11.02 / 5 / 0 | 10.60 / 5 / 0 | Both valid / none |
| qwen2.5 A | 11.47 / 3 / 0 | 6.08 / 3 / 0 | Both valid / none |
| qwen2.5 B | 14.76 / 3 / 1 | 7.95 / 3 / 0 | Both valid / none |
| qwen2.5 C | 8.05 / 3 / 0 | 7.25 / 3 / 0 | Both valid / none |
| qwen2.5 D | 7.39 / 3 / 0 | 6.92 / 3 / 0 | Both valid / none |
| qwen2.5 E | 9.71 / 5 / 0 | 9.66 / 5 / 0 | Both valid / none |

### Earlier cohorts retained, not pooled with v3

| Prompt/model | Runs | First-attempt accepted | After retry | Valid / inference attempts | Median / maximum | Observation |
| --- | --- | --- | --- | --- | --- | --- |
| v1 qwen3 | 5 | 5 | 0 | 5/5 | 8.53 / 16.27 s | Weak criteria and invented Python/OOP |
| v1 qwen2.5 | 5 | 0 | 0 | 0/5 | 60.07 / 60.07 s | Five AI_TIMEOUT; zero schema-evaluable responses; partial GPU placement |
| v2 qwen3 | 10 | 10 | 0 | 10/10 | 12.35 / 16.47 s | Prompt tightening alone did not fix goal assumptions |
| v2 qwen2.5 | 10 | 7 | 3 | 10/13 | 6.87 / 18.72 s | Capacity correction in A twice/B once; poor offline/goal adherence |

v1/v2 used JSON context in the user prompt; v2 added stronger instructions and
computed timing. Current CLI uses v3; old files preserve historical cohorts,
not a claim that today's invocation reproduces older prompt builders unchanged.

## 6. Quality review and limitations

Ratings are **Codex's inspection of fictional generated plans**, not measured
student task completion or human QA approval. JSON `quality_review` is initially
unrated by the CLI; the saved sweeps have separately recorded review annotations.
First-estimate arithmetic is automatic; realistic startability, observability,
capacity/energy/deadline awareness and goal alignment require judgment. Human QA
and actual task trials remain pending.

| Final model / case | First startable? | Criteria observable? | Capacity-aware overall? | Concrete evidence / issue |
| --- | --- | --- | --- | --- |
| qwen3 A | Yes, trivial start | Partial | Partial | 5-minute Hello World; replaces unspecified assignment with unrelated exercises, rather than reading its brief |
| qwen3 B | Yes | Partial | Partial | Review→practice→analysis; useful study direction, but not grounded in actual syllabus and some recall criteria vague |
| qwen3 C | Unknown without skill context | Yes | Partial | Concrete console outputs, but assumes Python and a calculator instead of choosing a focus/clarifying |
| qwen3 D | Yes | Partial | Yes | 10-minute project outline first, then materials/slides; later slide criteria vague |
| qwen3 E | Yes, outline start | Partial | Partial | Architecture→schema→CRUD→tests; invents Flask/user-post-comment domain and installation needs |
| qwen2.5 A | Yes | Partial | Yes | Reviews local assignment requirements first; later setup/coding criteria underspecified |
| qwen2.5 B | Yes, schedule start | Partial | Partial | Weekly schedule for three-day deadline; five full past papers in 45 minutes in run 1, ordering/effort questionable |
| qwen2.5 C | Partial | Partial | No in run 1; partial in run 2 | User-chosen familiar language is better, but run 1 requires coding websites/meetup; 15-minute complete project optimistic |
| qwen2.5 D | Yes | No | Partial | Outline first; later criteria “visually appealing”, “confidence”, friend/family availability assumed |
| qwen2.5 E | Unknown if tools absent | Mostly observable artifacts | No | Adds Flask-Login authentication and Heroku deployment; unrequested/cloud work is a major failure |

Neither final model explicitly asked a clarification question on C. The generator
returns only plans, not a production check-in decision union. Phase 3 must apply
the agreed one-essential-follow-up rule before generation when needed; do not
invent circumstances or add repeated interview loops.

No cloud request, authentication feature or Flask dependency was implemented.
Those terms above are **untrusted generated suggestions**, and illustrate why
schema-valid content must not be treated as approved product behavior. The
module does not automatically detect all such semantic violations. Do not save
or demonstrate these unsuitable suggestions as evidence of an offline-useful plan.

## 7. Representative validated plan

The sample below is the primary's D/run-1 v3 output, normalized by Pydantic.
It demonstrates the content shape and a useful first artifact, not perfect
criteria quality or proven completion within the estimates.

```json
{
  "quests": [
    {
      "title": "Outline the Presentation",
      "action": "Create a concise outline of the presentation based on the project topic.",
      "completion_criteria": "The outline includes key sections such as introduction, objectives, content, and conclusion, and is formatted in a clear, logical structure.",
      "estimated_minutes": 10,
      "difficulty": "easy",
      "hint": null
    },
    {
      "title": "Collect Supporting Materials",
      "action": "Gather all necessary materials for the presentation, such as slides, data, and references.",
      "completion_criteria": "All required materials are collected and organized in a logical folder or directory.",
      "estimated_minutes": 8,
      "difficulty": "easy",
      "hint": null
    },
    {
      "title": "Draft Key Slides",
      "action": "Write the first set of slides for the presentation, focusing on the most important points.",
      "completion_criteria": "The first set of slides includes the main content and is formatted in a way that supports the presentation.",
      "estimated_minutes": 12,
      "difficulty": "medium",
      "hint": null
    }
  ]
}
```

## 8. Error handling and automated evidence

Defaults: connect <=3 seconds, <=60 seconds per attempt, <=120 seconds total.
Each retry receives only the remaining total budget. Recheck the total deadline
after validation; discard late valid content. At most one correction for malformed
inner JSON, incomplete output, schema/domain failure. Correction contains fixed
validator codes and original context, never raw invalid model output/private error
values. No fabricated repair, indefinite retry or model failover.

QuestGenerationError distinguishes AI_INVALID_OUTPUT, AI_TIMEOUT,
OLLAMA_UNAVAILABLE, MODEL_UNAVAILABLE and AI_UPSTREAM_ERROR; it carries safe
attempt metrics and is recoverable by explicit user/config action. Connection,
missing-model, timeout and upstream HTTP/envelope errors do not get an automatic
format retry. A malformed Ollama HTTP envelope is an upstream failure; malformed
model text inside a valid envelope is a format-validation failure.

Actual failures: five initial backup timeouts; four backup capacity failures
across v2/v3, all corrected once. Live runs did not produce malformed inner JSON,
connection failure or two-invalid-output exhaustion. Those behaviors are mocked,
not asserted as observed model failures.

Actual final checks, from backend/:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
.venv/bin/python -m app.benchmark_ai --help
.venv/bin/python -c 'import sys; import app.benchmark_ai; assert "app.database" not in sys.modules; from app.main import app; from app.database import Base; assert set(app.openapi()["paths"]) == {"/api/health", "/api/ai/status", "/api/ai/generate"}; assert not Base.metadata.tables; print("PASS: CLI imports without database; unchanged API routes; zero application tables")'
```

**25/25 tests PASS: 19 new tests plus six unchanged scaffold smoke tests.**
Coverage includes missing/extra fields, invalid enum/blank actions/estimates/counts,
unauthorized state/coercions, malformed/fenced JSON, retry success/exhaustion,
connection/timeout/upstream errors, incomplete output, deterministic deadline
math and total-budget guards. An earlier 23-test run had one load-sensitive
60-ms wall-clock assertion failure; that test was replaced with a controlled
clock and budget-expiry cases. No production timeout was relaxed to hide it.
Dependency checks, CLI help and import/OpenAPI/no-table checks pass. There is no
configured backend linter. Existing live health/status/generation contracts were
checked separately with a fictional greeting; no source endpoint contract changed.

## 9. Reproduce on James's Windows laptop

Windows commands are provided, **not tested on that machine**. From repository
root, complete the existing README backend setup first. Verify `ollama list`
without downloading anything automatically. Close other inference workloads;
record the actual OS/CPU/RAM/GPU/driver/runtime and installed digests. Correct the
system timezone/clock before using the default current-time reference.

PowerShell:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
ollama stop qwen2.5:1.5b
ollama stop qwen3:1.7b
.\.venv\Scripts\python.exe -m app.benchmark_ai --model qwen3:1.7b --url http://127.0.0.1:11434 --timeout 120 --attempt-timeout 60 --repeats 2 --machine-label "James Windows demo laptop" --output ../docs/benchmarks/windows-qwen3-run1.json
ollama stop qwen3:1.7b
.\.venv\Scripts\python.exe -m app.benchmark_ai --model qwen2.5:1.5b --url http://127.0.0.1:11434 --timeout 120 --attempt-timeout 60 --repeats 2 --machine-label "James Windows demo laptop" --output ../docs/benchmarks/windows-qwen25-run1.json
ollama stop qwen2.5:1.5b
```

Use new filenames on subsequent runs. If a model is missing, record UNTESTED and
arrange installation separately. If a CPU-only machine exceeds 60 seconds, record
the failure first; a separately labeled experiment may increase both
`--attempt-timeout` and `--timeout`. Do not silently change reported budgets or
equate median Linux latency with Windows performance. CLI GPU/RAM detection is
best effort; fill unavailable hardware observations manually from that laptop.

Gracianne/James independently review each accepted plan; fill quality_review with
reviewer/evidence rather than automatically promoting VALID to a quality PASS.
For real offline proof, disconnect internet while keeping loopback/Ollama available,
run a new results file, and record disconnection evidence as instructed in
[OFFLINE_TESTING](OFFLINE_TESTING.md). DevTools Offline is not that test.

## 10. Recommendation and next gate

Keep **qwen3:1.7b**, non-thinking, temperature 0, seed 42, 4096 context and 1600
output-token cap for the next controlled iteration. Final accepted-plan rates
are tied, but the primary has fewer invalid attempts/retries and avoids the
backup's observed mandatory Heroku/auth scope additions. The backup is transport/
schema feasible **when resident alone**, not an approved semantic replacement.
Switch manually through configuration, never as a hidden retry/failover.

Reuse CheckInInput/QuestProposal/QuestPlan and generate_quest_plan in Phase 3;
call through the existing lifespan-managed adapter outside DB write transactions.
First implement the documented ready check-in and one essential clarification;
pass accepted goal details/summary/context explicitly (additive input fields),
never let a summary silently overwrite typed capacity/deadline or award XP.
Retain strict validation and failure telemetry without private text logging.
Replan later reuses QuestProposal but needs its separate 1–5 bound, not this
initial-only 3–5 QuestPlan. No product orchestration has been implemented here.

Recovery priority: requirements-first assignment decomposition; topic/language
choice instead of assumptions for C; a user-selected CRUD entity/stack with no
unasked auth/deployment; observable outputs and realistic effort. Rebenchmark
those cases with representative ready contexts before declaring the P0 AI gate
passed. A schema alone cannot establish these semantic properties, and repeated
prompt tightening/chat selection did not reliably solve them in this run.

**Phase 2 state-engine work can begin when explicitly authorized**, using isolated
fixtures independently of model quality. The broader AI quality/Windows/offline
gate remains open. No Phase 2 work, commit or push occurred in this phase.

## 11. Machine-readable evidence index

All artifacts contain fictional content only; human/private goals are not benchmark
inputs. Timing/attempt fields are original CLI measurements. Quality annotations
were added separately after content inspection and identify the reviewer.

| Artifact | Purpose |
| --- | --- |
| [linux-qwen3-initial.json](benchmarks/linux-qwen3-initial.json) | v1 primary A–E, one run each |
| [linux-qwen25-initial.json](benchmarks/linux-qwen25-initial.json) | v1 backup A–E, five retained timeouts/placement evidence |
| [linux-qwen3-v2.json](benchmarks/linux-qwen3-v2.json) | v2 primary, two runs per case |
| [linux-qwen25-v2.json](benchmarks/linux-qwen25-v2.json) | v2 backup solo, two runs per case/capacity retries |
| [linux-transport-probe.json](benchmarks/linux-transport-probe.json) | C: inline generate vs chat messages; exact request bodies |
| [linux-plain-context-probe.json](benchmarks/linux-plain-context-probe.json) | C: one plain-language context probe; exact request body |
| [linux-qwen3-v3.json](benchmarks/linux-qwen3-v3.json) | Final primary settings, two runs per case |
| [linux-qwen25-v3.json](benchmarks/linux-qwen25-v3.json) | Final backup settings, two runs per case |
