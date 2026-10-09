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

## 12. Phase 3 production pipeline recovery

**Status PARTIAL.** Two bounded primary-model sweeps exercised the actual
CheckInService → Ollama → semantic gate → SQLite pipeline on Matthew's Linux
machine, checkpoint aa9552e plus Phase 3 changes. Seven initial scenarios and
one replan per sweep; no frontend, actual task performance, Windows or disconnected
internet test. The backup was installed but **not benchmarked in Phase 3**.
All Phase 1B results above remain historical evidence, not current API inventory.

Runtime/hardware: Ollama 0.40.2, same installed primary digest/Q4_K_M and Linux
AMD A10-7860K / about 14.57 GiB RAM / GTX 1050 Ti 4096 MiB. Current hardware/runtime
snapshots are in the JSON files. Model metadata still reports 2.0B for the locked
qwen3:1.7b tag. Peak RAM was not measured; automated tests overlapped part of the
live sweeps, so latency is observed under development load, not a controlled
performance comparison.

The CLI uses temporary SQLite storage, never the product database. A–E reuse the
original goals/time/energy; A/C/D/E now ask a question and receive **explicitly
fictional fixture answers** about binary search/C++, Python list comprehensions,
SQLite/duplicate-XP presentation and book records/FastAPI/SQLite. B supplies local
sorting/asymptotic lecture notes. F is the specific three-FastAPI-login-tests goal;
G is a one-page SQLite explanation using local notes. H performs a synthetic
explicit completion then replans: its source is F in v1 and A in v2. This is not
a claim somebody performed those tasks. Clarification occurred on 4/7 initial
scenarios, not on B/F/G. No second question or fabricated user answer occurred.

Settings: native schema /api/generate, stream=false, think=false, temperature=0,
seed=42, num_ctx=4096, proposal num_predict=1600, review num_predict=300.
Proposal <=90 seconds / attempt <=60 / one format retry; review <=30 / no retry;
precommit pipeline <=120, intent lease=135. Fixed reference time constructs the
fictional deadlines; the production adapter uses actual current time for its
Python deadline context. Repeats are not identical frozen-time prompts.

Actual commands from backend/; existing filenames cannot be overwritten:

```bash
.venv/bin/python -u -m app.benchmark_pipeline --model qwen3:1.7b --url http://127.0.0.1:11434 --reference-time 2026-10-09T23:00:00+08:00 --machine-label 'Matthew Linux development machine' --output ../docs/benchmarks/linux-phase3-qwen3-v1.json
.venv/bin/python -u -m app.benchmark_pipeline --model qwen3:1.7b --url http://127.0.0.1:11434 --reference-time 2026-10-09T23:00:00+08:00 --machine-label 'Matthew Linux development machine' --output ../docs/benchmarks/linux-phase3-qwen3-v2.json
```

For Windows, from backend/ use
`.\.venv\Scripts\python.exe -m app.benchmark_pipeline --model qwen3:1.7b --output ../docs/benchmarks/windows-phase3-new.json`.
This command is provided for reproduction, not tested on James's laptop. Do not
download missing models automatically. CLI exit 0 means measurement completed,
not semantic acceptance; content/human review remains separate.

| Measured gate cohort | Schema-valid / first attempt | Pipeline saved | Codex content inspection acceptable | Proposal-request median / max | Full workflow median / max | Retry / timeout operations |
| --- | --- | --- | --- | --- | --- | --- |
| v1 | 8/8 / 8/8 | 7/8 | 2/8 (A,B) | 9.53 / 16.05 s | 11.56 / 18.34 s | 0/8 / 0/8 |
| v2 | 8/8 / 8/8 | 2/8 | 1/8 (A) | 9.64 / 12.14 s | 10.26 / 12.33 s | 0/8 / 0/8 |

Proposal-request timing sums measured proposal-attempt latencies, not review.
Full workflow includes context/clarification, reservation, proposal, applicable
review and persistence. Rejected plans can skip review, so a lower median does
not mean better quality. There were 16 proposal calls plus 9 review calls across
the two cohorts. These small samples are not reliability proof. Codex content
inspection is neither independent human approval nor actual task execution.

| Case | v1 saved / seconds | v2 saved / seconds | Observed issue |
| --- | --- | --- | --- |
| A assignment | Yes / 18.34 | Yes / 11.53 | Grounded binary search, two tests and recorded output; estimate not task-timed |
| B exam | Yes / 11.28 | No / 8.95 | v2 invents Python and uses review-only criteria |
| C skills | Yes / 11.85 | No / 11.00 | Replaces existing examples with invented inputs |
| D presentation | Yes / 9.54 | No / 7.88 | Generic steps omit the supplied SQLite/duplicate-XP focus; v1 subjective readiness |
| E CRUD | No / 8.15 | No / 9.52 | Initializes a new project despite supplied existing project |
| F three tests | Yes / 10.45 | No / 8.33 | Only two tests; v2 invents HTTP 200 behavior |
| G explanation | Yes / 12.16 | Yes / 12.27 | v1 subjective criteria; v2 supplies SQL examples without an explanation |
| H replan | Yes / 16.35 | No / 12.33 | v1 invents response codes; v2 repeats the completed binary-search action |

Both replan operations preserved completed history and XP; v2 rejection retained
the original business plan. The one-call local reviewer incorrectly approved
several v1 plans and v2 G with high confidence. Stronger deterministic checks
reduced false saves but do not establish general semantic reliability.

**Final code gate grounded-quests-v2.1:** added an explanation-omission check after
inspecting G. This has deterministic regression coverage and was applied to the
saved proposals without new inference or persistence. It passes only A among
the eight v2 proposals, rejecting G as unrelated. That is a post-run necessary-
condition recheck, **not a third live benchmark or a measured new save rate**.
The two JSON artifacts preserve all original attempts/timings/saved outcomes and
add separately labeled Codex content review and post-run deterministic recheck.
`human_quality_review` remains unfilled for independent team QA.
Final replan-grounding wiring also forwards the user change reason; that was
verified with mocks after the sweeps, without another live measurement.

Evidence:
[v1 actual pipeline results](benchmarks/linux-phase3-qwen3-v1.json),
[v2 actual pipeline results](benchmarks/linux-phase3-qwen3-v2.json).
Remaining semantic risks: unknown technologies/topics, paraphrased duplicates,
plausible-looking but invented API behavior, broad-goal classification mistakes,
false positives from conservative literal/material rules and inaccurate effort.
Do not weaken validation to turn rejected content into saved demo plans. The
next reviewed recovery needs more reliable grounded generation or manually
evaluated backup configuration; no further sweeps/tuning were performed here.

Final deterministic checks from backend/:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q app tests
git diff --check
```

90/90 tests passed (57 preserved with updated schema/route expectations, 33 new).
An early integration run failed imports due to missing new model declarations;
an expanded run had one invalid stale-replan fixture. Both were corrected and the
complete suite rerun successfully. Migration/data preservation, malformed output,
semantic rejection, concurrency, failure rollback, cancellation, expiry/fencing,
replay after new-process restart and local-only diagnostics are tested with mocks/
temporary SQLite. This does not prove live semantic success or disconnected AI.

## 13. Phase 3B everyday-goal hotfix

**Status: PARTIAL.** This fixes concrete false-rejection/error-recovery bugs; it does
not establish reliable semantic quest generation. Default qwen3:1.7b is unchanged.

### Diagnosis and safeguards

The exact reported cooking input returned valid JSON before the fix in 8.95 s,
but `unobservable_criteria` rejected it before local review. It selected an
unspecified flour/sugar/spice, mixed it with liquid and proposed tasting that base:
that particular output was not a useful safe cooking plan. The rule was also
software-biased: physical outcomes and short concrete actions could not pass.
Generic cooking skipped clarification, so a missing ingredient fact was invented.
Format retry occurred before quality checking, leaving no automatic correction
for semantic failures. Frontend semantic errors incorrectly blamed insufficient
user detail. A Develop/Document two-test plan was falsely counted; an explicit
FastAPI stack was falsely treated as not grounding Python.

Now generic cooking asks one focused dish/available-ingredients question. Named
ingredients/dishes proceed without that question. Physical arrangement, plating,
serving and storage states count as observable. Bounded medium starts are not
automatically wrong at low energy. Negated external/heat steps are not requirements.
Hard checks retain named deliverables, test counts, capacity, existing materials,
completed-action repeats and external dependencies, plus explicit no-heat,
ingredient-only, vegetarian, no-auth/deployment/existing-runner constraints and
raw-food tasting violations. These literal checks cannot establish general safety
or relevance. No rejected candidate reaches business persistence or earns XP.

One shared correction covers format or quality failure (two proposals maximum);
review may run once per candidate. Low-confidence review triggers correction,
then typed AI_REVIEW_UNCERTAIN, not an assertion that the user or plan is wrong.
The gate still fails closed; it never blindly waives uncertain grounding. Timeout
120 s total / 60 per proposal / 30 per review / 3 connect; no transport retries,
model switching or inference-held SQLite write transactions. Existing intents,
revision fencing, atomic commit and public filtering are unchanged.

### Measured comparison

All inputs/answers are fictional; Matthew Linux development machine: AMD
A10-7860K, 15,640,678,400 bytes RAM (14.57 GiB), GTX 1050 Ti detected with 4096 MiB
VRAM plus integrated Radeon R7; Python 3.14.7, Ollama 0.40.2. Full detected hardware,
installed model identifiers and resident state are recorded in each JSON artifact.
Settings: native /api/generate JSON schema; think=false; temperature=0; seed=42;
num_ctx=4096; proposal num_predict=1600; review num_predict=300. Backup not tested.

| Cohort | Structure / first attempt | Saved | Corrected operations | Timeouts | Full workflow median / max |
| --- | --- | --- | --- | --- | --- |
| Before, v2.1 | 12/12 / 12/12 | 3/12 (25%) | 0/12 | 0/12 | 9.90 / 12.18 s |
| Full hotfix, v3b.1 | 12/12 / 12/12 | 3/12 (25%) | 10/12 | 0/12 | 17.58 / 24.21 s |
| Final physical-only, v3b.2 | 3/3 / 3/3 | 3/3 (100%) | 0/3 | 0/3 | 12.76 / 13.13 s |

Full v3b.1 run used initial-quests-v3b.1. Final v3b.2 changed only physical-state
phrasing before the targeted live run; combined no-login-or-deployment wording
was subsequently covered by deterministic regression. These are different cohorts,
not a measured 100% general success rate. Earlier draft results are retained.
A targeted-run filter mistake completed one extra A then was interrupted during B;
that partial artifact is retained and excluded from comparison statistics.
The old Phase 3 v2 cohort saved 2/8 and content inspection approved 1/8. Its timing,
reference and H source differ; it is historical evidence, not a controlled comparison.

| Case | Before saved / seconds | Full v3b.1 saved / seconds | Final physical saved / seconds | Final full rejection codes |
| --- | --- | --- | --- | --- |
| A | No / 10.11 | No / 15.65 | Not rerun | unobservable_criteria |
| B | No / 8.43 | No / 17.91 | Not rerun | unobservable_criteria |
| C | No / 10.40 | Yes / 12.25 | Not rerun | None |
| D | Yes / 9.95 | No / 13.94 | Not rerun | unobservable_criteria, unrelated |
| E | No / 8.83 | No / 19.45 | Not rerun | duplicate_or_contradiction, explicit_constraint_violated |
| F | No / 7.28 | No / 19.12 | Not rerun | duplicate_or_contradiction, explicit_constraint_violated, unsupported_assumption |
| G | No / 9.84 | No / 17.13 | Not rerun | unobservable_criteria, unrelated |
| I | No / 8.53 | No / 17.25 | Yes / 13.13 | unobservable_criteria |
| J | Yes / 10.47 | Yes / 12.89 | Not rerun | None |
| K | No / 7.61 | No / 19.81 | Yes / 12.76 | unobservable_criteria |
| L | Yes / 11.06 | Yes / 18.05 | Yes / 10.48 | None |
| H | No / 12.18 | No / 24.21 | Not rerun | duplicate_or_contradiction |

A–H retain the eight Phase 3 scenarios; I cooking, J Python study, K constrained
no-cook snack, L five-minute desk tidying. A/C/D/E clarified in both full runs;
I additionally clarified after the fix. B/F/G/J/K/L did not ask a question.
H used the first available saved line: presentation before, Python skills after,
so those replans are not paired-content comparisons. Both preserved history/XP
on rejection. Exact candidates, stage codes, questions, retries and timings are
in artifacts. Small samples under ordinary development load are not reliability
or controlled performance proof; final physical latency overlapped regression work.

### Content inspection and remaining failures

Codex inspection is separate from the local-model review; independent human QA
and actual task execution remain pending. Before: A and K were useful despite
false deterministic rejections; 2/12 acceptable, 2 partial, 8 unacceptable under
this inspection. Full hotfix: 0/12 fully acceptable, 6 partial, 6 unacceptable.
Final physical run: all three partially useful, none fully satisfactory. These
subjective ratings do not prove a population-level quality change.

- Cooking now uses supplied no-cook sandwich ingredients and saves; it redundantly
  washes already washed lettuce and repeats cheese placement/assembly/plating.
- Constrained snack uses only bread/tomato/cheese, no heat/shopping; repeated
  arrangement/assembly and awkward hints weaken the quest framing.
- Household sorting is relevant, but the first quest repositions storage already
  beside the desk. The local reviewer wrongly approves these redundancies.
- Python practice still invents input types or leaves transformation unspecified.
- Presentation still omits SQLite/duplicate-XP focus; CRUD reinitializes an existing
  project; login testing supplies two instead of three tests and invents HTTP codes.
- Replanning repeats completed work; hard checks reject it without history/XP loss.

False-positive rule evidence is distinct from whole-plan usefulness: plate/serving
wording is observable even in a poor plan. Correcting that rule does not make
the entire cooking output good. Uncertain review is classified accurately and
bounded, but a confident reviewer can still be wrong.

Representative final saved cooking content for team review:
1. “Wash the lettuce, spread the sliced bread, and place the cheese on top of the
   bread.” Criterion: ingredients arranged on a plate; 5 min/easy.
2. “Place the cheese on the bread, add the lettuce, and form the sandwich…”
   Criterion: assembled sandwich ready for consumption; 3 min/medium.
3. “Place the assembled sandwich on a plate and present it…” Criterion: sandwich
   on a plate ready to serve; 2 min/easy.
This shows real grounding improvement over the raw-flour base, but weak sequencing.

### Reproduce (Linux or activated Windows backend environment)

From backend/, use `.venv/bin/python` on Linux or activated `python` on Windows.
Never overwrite a results filename; the command refuses existing output paths.

```bash
python -m app.benchmark_pipeline --hotfix-cases --reference-time 2026-10-10T00:30:00+08:00 --machine-label "James Windows demo laptop" --output ../docs/benchmarks/windows-hotfix.json
python -m app.benchmark_pipeline --hotfix-cases --case I --case K --case L --reference-time 2026-10-10T00:30:00+08:00 --output ../docs/benchmarks/physical-check.json
```

Current code is v3b.2, so new results are not a recreation of the old v3b.1 code.
No Windows, actual internet-disconnection, backup-model or human task trials were
performed in this hotfix. Initial dependencies/models must already be installed.

Evidence: [before](benchmarks/linux-phase3b-before.json),
[exact cooking before](benchmarks/linux-phase3b-cooking-before.json),
[draft](benchmarks/linux-phase3b-after-draft.json),
[full v3b.1](benchmarks/linux-phase3b-after.json),
[final physical v3b.2](benchmarks/linux-phase3b-physical-final.json),
[interrupted diagnostic](benchmarks/linux-phase3b-interrupted.json).

Checks: 107 backend regression tests, frontend typecheck/build, 5 boundary tests
and 14 Chromium integration checks passed. Browser checks used real React/FastAPI
and temporary SQLite with mocked Ollama; they are separate from the live CLI sweeps.
Dependency check, compilation and diff checks passed. No model download, default
model change, schema/state-engine change, commit or push.

Recommendation: keep the existing model and safeguards for this hotfix; team QA
must review practical sequencing. General semantic-quality recovery remains
PARTIAL, and accepted/rejected counts must never be presented as usefulness rates.

### Resumed presentation diagnosis (v3b.3 gate / v3b.2 prompt)

The preserved `/tmp/phase3b-final-tests.log` records 107/107 OK; its process exited
0. A fresh unchanged-tree run also passed 107/107 with exit 0. No retained output
explains the reported later exit 1, so its cause cannot be asserted. A standalone
/tmp reproduction script failed `ModuleNotFoundError: app` until PYTHONPATH=.
was set: that observed failure is runner configuration, not a backend regression.

Requested scenario A: a five-minute AI introduction for classmates, research,
three slides and practice; 60 minutes/medium. Before: schema-valid after one
correction, saved in 28.59 s; four quests researched basics and made three slides
but omitted practice. This confirmed a material omission despite reviewer approval.
After enforcing explicit slide/practice coverage and grounded prompt guidance:
schema-valid after correction, rejected in 21.62 s with unobservable_criteria and
unsupported_assumption. Candidate includes research, three slides and practice,
but invents PowerPoint/Google Slides and subjective engaging/clear rehearsal success.
The browser's separate real generation attempt also returned recoverable rejection.

Requested scenario B: present a complex topic known nothing about; 240 minutes/low.
Before: no clarification; schema-valid proposals invented topics/software or
deferred choosing a topic; rejected in 16.87 s (final unobservable_criteria; first
also unsupported_assumption). The classifier omitted the verb present and relied
on word count. Now it asks: “What is the presentation topic and the main result
you need to communicate?” Check-in is saved awaiting an answer; no questline,
model output or generation latency exists after this fix. No answer was invented.
Full local diagnostics: /tmp/phase3b-presentations-before.json and
/tmp/phase3b-presentations-after.json; they are not production logs.

Browser command from frontend/: `node tests/core-flow.mjs --live-ai`. The 14
existing mocked-Ollama cases pass, followed by real B clarification, real A
rejection, and a real constrained no-cook snack save/full completion/refresh.
All three actual generated snack quests were completed via UI: Prepare the Base
(10 XP), Assemble the Snack (20 XP), Serve the Snack (10 XP). Profile changed
50→90 XP, level 1, questline remained completed after refresh. Completion clicks
are synthetic test acknowledgements, not evidence somebody physically made food.
Real content still includes redundant plating and assumptions about cheese shape.
The live test uses no seeded/fabricated plan; it tries at most the presentation
and the documented constrained-snack goal. Results/screenshots and isolated SQLite
are local at /tmp/quest-phase4b-yYsvcP. The recorded console count of 17 totals
14 mocked regressions plus 3 live observations; future output separates those.

Final backend checks: 111/111 passed, including new pure-policy and orchestration
regressions for missing topics and omitted practice. Frontend typecheck/build,
5 boundary tests, compilation, dependency checks and diff check passed.
No default model, state-engine/schema, PRD or application frontend-flow changes.
Status remains PARTIAL: a real complete local UI loop works, but the requested
specific presentation still fails safe generation and reviewer judgments remain
unreliable. Windows and disconnected-internet trials remain untested.

## 14. Phase 3C bounded semantic recovery

**Status: PARTIAL; release-quality target not met.** Current prompt/gate are
`initial-quests-v3c.4` / `grounded-quests-v3c.4`. Default model remains qwen3:1.7b.
No state-engine, database, PRD or production frontend changes were needed.

### Confirmed causes and corrections

| Evidence | Classification and implemented response |
| --- | --- |
| Before C rejected a loop that prints 1–10; before A vetoed “a tool like PowerPoint” | False positives: printed program outputs are observable; explicitly optional recognized tool examples are allowed, while installation/accounts/mandatory unprovided tools remain blocked. |
| Before B saved invented foods without asking; E proceeded without a topic | Essential unknowns: food availability and topic now use the existing focused question. Terminal punctuation no longer defeats format-only goal classification. Original goal and answer persist separately. |
| Subjective criteria or vague actions in an otherwise valid plan | Repairable: exact quest-index/field patches replace only bad action/criteria content. Python rejects extra, missing or duplicate targets and revalidates the entire merged plan. |
| Added foods/supplies, omitted counts, invented endpoint behavior, repeated completed work | Hard violations: never waived by model review; one full correction can be attempted before recoverable rejection. Initial 3–5/replacement 1–5, capacity and difficulty screens remain. |
| Model opinions about borderline estimates/difficulty or verified optional tools | Advisory/checked evidence: cannot override deterministic hard checks. Uncertain relevance still receives one correction and fails closed if unresolved. |
| Native patch HTTP 400 and internally contradictory review JSON during drafts | Implementation defects: Ollama 0.40.2 rejects `items:false`; object-valued `items` works. Native review branches now enforce consistent decision/issues/findings, with Python validation still required. |

These necessary screens do not prove relevance or safety. Duplicate exact criteria,
premature slide-result criteria on a research-only stage, and known subjective
grading receive regression coverage. Paraphrased duplicates and novel invented
requirements remain limitations. The model can still confidently approve a poor
plan; native decision consistency only fixes malformed review output.

One shared correction allowance: maximum two proposal/repair calls and two compact
reviews, 120 seconds total, 60 per generation/repair, 30 per review, 3 connect.
No transport retry, automatic model switching or inference-held write transaction.
Scoped repair cannot change titles/count/order/estimates/difficulty/hints or valid
neighboring content. Persistence, revisions, idempotency and XP remain unchanged.
Failed generation leaves a retryable check-in and no business questline or XP.

### Paired live scenarios and measurements

Same original A–F goals/time/energy before and after; G adds the existing-runner
three-test goal to make six actionable generation cases. F awaits clarification
and is excluded from generation statistics. B now asks available foods; the CLI
answers with fictional bread/tomato/cheese already available, no-cook sandwich.
E now asks the topic; the fictional answer is an AI introduction to classmates
using local materials. These are supplied QA answers, not fabricated production
answers. A/C/D/G proceed directly; F gets no invented answer or inference call.
The supplied six scenarios contain only five potentially actionable goals plus F;
G is explicitly additional, not silently included as an original requirement.

| Case | Before saved / seconds | Final saved / seconds | Final correction / outcome |
| --- | --- | --- | --- |
| A AI presentation | No / 22.16 | Yes / 21.32 | Targeted criterion repair; covers three slides/practice but adds perfection/timing requirements. |
| B tired cooking | Yes / 11.39 | No / 10.44 | Ingredient clarification then targeted repair; still `unobservable_criteria`. Original save invented foods and repeated assembly. |
| C Python loops | No / 17.14 | Yes / 13.49 | Targeted criterion repair; observable local loop exercises. Original final `unobservable_criteria` was a false rejection. |
| D desk cleaning | Yes / 19.29 | Yes / 18.46 | Full correction of criteria/unmentioned supplies; still unnecessary labels and unconfirmed ordinary cleaning tools. |
| E three slides/one rehearsal | No / 25.04 | Yes / 11.29 | Topic clarified, first candidate saved; preserves requested count and timed aloud rehearsal. |
| F unknown presentation topic | No inference | No inference | “What is the presentation topic and the main result you need to communicate?” Check-in saved awaiting answer. |
| G three existing-runner tests | No / 21.49 | No / 18.65 | Full correction exhausted; `duplicate_or_contradiction`, `unsupported_assumption`: two tests plus invented 200/401 and token fields. |

| Metric (six generation operations) | Before v3b.3 | Final v3c.4 |
| --- | --- | --- |
| First proposal structurally valid | 6/6 (100%) | 6/6 (100%) |
| Last attempt structurally valid | 6/6 | 6/6 (including scoped merged repairs) |
| Persisted plan | 2/6 (33.3%) | 4/6 (66.7%) |
| Saved without any correction | 1/6 | 1/6 (E) |
| Operations with correction | 5/6 | 5/6: 3 targeted, 2 full |
| Timeouts | 0/6 | 0/6 |
| Full workflow mean / median / max | 19.42 / 20.39 / 25.04 s | 15.61 / 15.98 / 21.32 s |
| Codex-inspected acceptable final candidates | 1/6 (C, rejected) | 2/6 (C/E, saved) |
| Saved and Codex-inspected acceptable | 0/6 | 2/6 |
| Confirmed known hard-requirement compliance / violation / uncertain | 2 / 4 / 0 | 3 / 1 / 2 |

Hard-requirement inspection considers original user facts, explicit quantities,
invented mandatory prerequisites and actual local resources. Final B is grounded
but has bad criteria; A/D have uncertain additional requirements; G violates known
requirements. Passing implemented hard screens (four saves) is separate from this
content inspection and is not proof of complete compliance. Ratings are by the
Codex code author, **not independent human QA** or actual task execution; human
review fields remain blank. Conservatively, only C/E are fully acceptable under
this inspection. The 5/6 saved/useful target is not achieved.

One run per case, same primary model/settings on the Linux development laptop:
AMD A10-7860K, 14.57 GiB RAM, detected GTX 1050 Ti 4096 MiB plus integrated R7,
Python 3.14.7, Ollama 0.40.2. Native `/api/generate`, `think:false`, temperature 0,
seed 42, context 4096, generation/repair 1600 tokens, review 300 tokens. Different
run timestamps/normal development load and deterministic sampling do not make
these controlled performance trials or reliability estimates. Backup, Windows,
internet-disconnected operation and human task timings were not tested.

### Actual examples for team review

Saved C: “Write a simple loop that counts up from 1 to 10 and prints each number.”
Criterion: “The loop should correctly print numbers from 1 to 10.” 5 min/medium.
Next stage computes the sum of 1–10 with a loop and outputs the result.

Saved E: “Rehearse the presentation aloud using a timer, recording the duration of
the rehearsal in text.” Criterion: “The rehearsal must be completed within the
session time and the duration must be noted in the output.” 10 min/medium.
This is a real observable run, though the session-time wording is redundant.

Saved A still requires a “realistic, natural, and accurate” speech with “no pauses
or repetitions” and adds five minutes per slide. Those are unrequested constraints,
not evidence of usefulness. B's repaired criterion repeats the imperative “Place
a layer of cheese…” instead of stating the resulting state. D adds labeling;
G asserts response codes and token fields not supplied by the user. These examples
explain why an improved save rate is insufficient to declare PASS.

### Reproduce and retained evidence

From backend/ with the existing environment (Linux `.venv/bin/python`; activated
Windows `python`), choose a new output filename:

```bash
python -m app.benchmark_pipeline --reliability-cases --model qwen3:1.7b --url http://127.0.0.1:11434 --capture-native --reference-time 2026-10-10T02:37:44.115323+08:00 --machine-label "James Windows demo laptop (when actually executed there)" --output ../docs/benchmarks/windows-phase3c.json
```

`--capture-native` records response envelopes only for this developer CLI's
hardcoded fictional cases. It does not add production logging, reveal prompts or
return future quests through public APIs. The CLI uses a temporary QA database,
not application state. Exit 0 means measurements completed, not semantic PASS.

Paired evidence: [before](benchmarks/linux-phase3c-before.json),
[final v3c.4](benchmarks/linux-phase3c-final-v4.json).
Intermediate cohorts remain preserved: [v3c.1](benchmarks/linux-phase3c-after.json),
[v3c.2](benchmarks/linux-phase3c-after-v2.json),
[v3c.3](benchmarks/linux-phase3c-final.json).
The v3c.3 run saved 5/6 but had copied premature criteria and subjective grading;
it is superseded, not proof the target was met. Diagnostic probes are excluded
from cohort statistics: [native patch incompatibility](benchmarks/linux-phase3c-native-diagnostic.json),
[presentation probe](benchmarks/linux-phase3c-review-diagnostic.json),
[contradictory review](benchmarks/linux-phase3c-review-g-diagnostic.json).
Raw metrics are preserved; paired artifacts add separately labeled Codex
inspection, without filling human QA fields.

### Regression and browser evidence

From backend/: `.venv/bin/python -m unittest discover -s tests -v`: **134/134 OK**,
including 111 existing tests and targeted repair/classification/native-schema
regressions. Early runs exposed obsolete full-plan retry fixtures and a real
punctuation/clarification bug; both were corrected. `-m pip check` and
`-m compileall -q app tests` passed.

From frontend/: `npm run typecheck`, `npm run build`, and
`node --test --test-isolation=none tests/validation.test.mjs tests/campaign.test.mjs`
passed (11/11 tests). `node tests/core-flow.mjs --live-ai` passed **16 mocked-Ollama
browser regressions** and two separate live observations: missing-topic
clarification and an actual Qwen3 presentation saved/completed/refreshed. The live
campaign awarded 50 XP once across three UI completions: profile 50→100, level
1→2, completed after refresh. These are synthetic explicit acknowledgements,
not evidence that somebody performed the presentation. That separate candidate
still adds timed-run requirements to research/slides and subjective delivery;
integration PASS is not semantic PASS. Local browser evidence:
`/tmp/quest-phase4b-vkSCYF`. Diff whitespace checks passed.

Recommendation: retain the primary model and reusable bounded repair boundary;
do not claim release-ready general generation. Team review is needed for A/D;
B's repair still fails and G's inferred API behavior remains unsafe to persist.
No larger-model change, blind fallback, frontend-fabricated plan or further phase
was introduced. Semantic reliability remains the release blocker.

## 15. Phase 3D essential-only acceptance

**Reliability status: PARTIAL.** The requested policy simplification is implemented
and regression-verified, but the six-case run still rejects a specific test-writing
goal for genuine missing outcomes/invented behavior. Save rate is not usefulness.
Current policy is `essential-constraints-v3d.1`; prompt `initial-quests-v3c.4`,
primary model and generation settings are unchanged.

### Acceptance policy

Production check-in generation and replanning no longer call the semantic reviewer.
Strict JSON/Pydantic validation and deterministic essential checks precede the
existing atomic persistence transaction. Subjective criteria, vague/stylistic
wording, optional tools/resources, copied criteria, minor sequencing and borderline
effort/difficulty judgments are diagnostic warnings. They do not trigger rejection,
repair or additional model calls. Unknown broad relevance is not submitted to
model self-approval. Existing focused clarification remains unchanged.

Blocking: missing/extra/invalid fields, initial 3–5/replacement 1–5, positive bounded
durations and difficulty enum, first estimate beyond explicit session capacity,
known explicit outcome/count violations, material contradictions, mandatory new
external dependencies, unsafe food instructions and repeated completed actions.
Optional suggestions cannot waive user prohibitions such as no downloads or a
later mandatory prerequisite. Obviously impossible whole-app ten-minute promises
remain distinct from minor effort opinions. Known literal screens are not a
general proof of semantic compliance.

At most two generation calls share the existing 120-second budget, 60 per attempt,
3 connect; zero approval reviews and no transport retry. A blocking candidate gets
one complete corrected proposal. No fallback quests, new model/dependencies,
database/frontend/schema changes or automatic model switching. Warning codes remain
internal; raw goals/plans are not logged or exposed through public diagnostic DTOs.
Legacy review/patch helpers remain available for explicit developer experiments,
but are absent from the production acceptance path. Public contracts stay intact.

### Actual paired results

Same A–E/G actionable goals, time/energy and fictional B/E clarification answers as
Phase 3C; F tests missing-topic clarification without an invented answer. Measurements
use a temporary QA database and native Qwen3 on Matthew's Linux machine, Ollama
0.40.2, AMD A10-7860K, 14.57 GiB RAM, detected GTX 1050 Ti 4 GiB. Backup/Windows,
internet-disconnection and human task execution were not tested. Temperature 0,
seed 42, context 4096, generation token cap 1600, think=false. One run per case;
ordinary load/GPU sampling are not controlled reliability or performance proof.

| Case | Phase 3C saved / seconds | Phase 3D saved / seconds | Final inspection / remaining issue |
| --- | --- | --- | --- |
| A AI introduction | Yes / 21.32 | Yes / 15.19 | Partial: all requested outcomes, but exact five-minute recorded speech adds precision/possibly recording overhead. |
| B tired cooking | No / 10.44 | Yes / 8.64 | Usable: available ingredients only, no heat, three small preparation/assembly actions. |
| C Python loops | Yes / 13.49 | Yes / 9.07 | Usable: local counting/summing exercises; first two examples overlap slightly. |
| D clean desk | Yes / 18.46 | Yes / 17.01 | Usable after one correction: no special unprovided supplies; tidiness criteria remain subjective. |
| E three slides/one rehearsal | Yes / 11.29 | Yes / 9.62 | Usable after topic answer: slide count and actual timed aloud rehearsal preserved. |
| F unknown topic | Clarification only | Clarification only | Correct focused topic question; no inference. |
| G three tests | No / 18.65 | No / 19.99 | Essential rejection: `duplicate_or_contradiction`, `unsupported_assumption`; only two tests and invented response codes. |

| Metric (six actionable cases) | Phase 3C final | Phase 3D |
| --- | --- | --- |
| First-proposal structural validity | 6/6 | 6/6 |
| Saved plans | 4/6 (66.7%) | 5/6 (83.3%) |
| Saved without correction | 1/6 | 4/6 |
| Corrected operations / timeouts | 5/6 / 0 | 2/6 (D/G) / 0 |
| Mean / median / max full-workflow latency | 15.61 / 15.98 / 21.32 s | 13.25 / 12.41 / 19.99 s |
| Codex-inspected usable saved candidates | 2/6 | 4/6 (B/C/D/E) |
| Confirmed known hard-requirement compliance / violation / uncertain | 3 / 1 / 2 | 4 / 1 / 1 |

All five saves passed implemented essential checks. Content inspection separately
confirms known requirements for B/C/D/E, marks A uncertain because of added recording
precision, and identifies G's rejected contradiction. These findings do not prove
general compliance. Phase 3D's practical-usefulness rubric allows minor wording or
effort imperfections while requiring a concrete goal contribution and no critical
invented prerequisite. Thus the two inspection cohorts are informative but not a
blinded identical-rubric quality experiment. Ratings are the Codex code author's
inspection, **not independent human QA**; human review fields remain blank.

The captured native calls confirm **eight proposal calls and zero reviews**.
Subjective warnings occurred without inference correction. D's first candidate
required an unmentioned microfiber cloth; the single full correction removed that
special prerequisite. G exhausted the same one correction without a save. No
rejected proposal created business quest rows or XP.

### Representative real output for team review

Saved B stages: Prepare the Sandwich Base → Add Tomato and Cheese → Assemble the
Sandwich. Middle action: “Place a slice of tomato on one half of the bread, then
add a layer of cheese on top.” Criterion: “Tomato and cheese are placed on the
bread as a sandwich base.” Each stage is 1 min/easy. Cutting already sliced bread
is unnecessary but a small grounded preparation step, not a safety contradiction.

Saved C action: “Create a small program that calculates the sum of numbers from
1 to 10 using a loop.” Criterion: “The program should output the sum as 55.”
5 min/medium. The model proposes exercise content; application XP/state still
comes exclusively from backend code.

Saved E action: “Rehearse the presentation aloud using a timer, noting the elapsed
duration in text.” Criterion: “Complete the rehearsal within the session time,
recording the duration in text.” 10 min/medium. This covers the explicit rehearsal,
though session-bound wording is redundant. Saved A's “exactly 5 minutes” criterion
and recording interpretation need team judgment. G's “200 OK” expectation and two
test-writing stages are unsupported and correctly rejected, not stylistic concerns.

Evidence: [Phase 3D raw candidates, warnings and measurements](benchmarks/linux-phase3d-qwen3.json),
[Phase 3C baseline](benchmarks/linux-phase3c-final-v4.json). Existing artifacts are
preserved. Reproduce from backend/ using the existing environment; choose a new
output filename:

```bash
python -m app.benchmark_pipeline --reliability-cases --model qwen3:1.7b --url http://127.0.0.1:11434 --capture-native --reference-time 2026-10-10T02:37:44.115323+08:00 --machine-label "James Windows demo laptop (only when run there)" --output ../docs/benchmarks/windows-phase3d.json
```

### Regression verification

Backend: `.venv/bin/python -m unittest discover -s tests -v`: **141/141 OK**, seven
new essential-policy/persistence regressions and updated expectations for the
authorized warning-only policy. The initial unchanged-expectation run failed
20 assertions and one attempt-index access because it expected reviews/subjective
repairs; these were updated, not waived. Existing state, rollback, migration,
idempotency and privacy tests passed. Dependency and compilation checks passed.

Frontend: `npm run typecheck`, `npm run build`, and
`node --test --test-isolation=none tests/validation.test.mjs tests/campaign.test.mjs`
passed (11/11 tests). `node tests/core-flow.mjs --live-ai`: **16 mocked-Ollama browser
regressions passed**, then real topic clarification and a real Qwen3 presentation
save/three-stage completion/refresh passed. XP profile 50→100, level 1→2, line
completed after refresh. Synthetic completion acknowledgements are not actual
presentation execution or human quality approval. Local evidence:
`/tmp/quest-phase4b-rUJMZ4`. The separate browser candidate still has subjective
visual/delivery criteria, now non-blocking as requested. Diff/link checks passed.

The targeted gate removal is verified. Broader generation reliability remains
PARTIAL because G still fails an essential requirement and accepted content varies.
No PRD, database schema, XP engine, Campaign Map, default-model change, commit or
push. Stopped after Phase 3D for review.

## 16. Adaptive campaign sizing: 2–6 stages

Approved post-PRD feature: initial 2–6, chosen by the existing local generation
call from the complete goal's scope. No separate classifier or deterministic
size-by-session rule. Prompt `adaptive-stages-v2` asks for the smallest useful
count, combines tiny related actions for simple goals, avoids filler and repeated
placeholder titles. Replans use 1..(6−completed), preserving all history/XP and
allowing a single remaining action. The trusted service separately enforces six
total stages. Existing longer legacy histories are not truncated.
No-history replans require two remaining stages; with history one is allowed.

Duration bounds are unchanged: estimates are integers 1–1440; only the first must
fit available minutes. There is no campaign-sum <=session rule. Low-energy effort
guidance remains non-blocking per Phase 3D. Models, temperature 0, seed 42, context
4096, 1600 generation tokens, think=false, 120s total/60s attempts/3s connect and
one correction remain unchanged. No mandatory reviewer calls.

Two fictional goals, one run each per prompt revision, on the previously recorded
Linux machine/Ollama 0.40.2. Simple: no-cook sandwich with already available bread,
tomato and cheese, no stove/shopping; 10 minutes/low. Complex: local Python loop
study guide with explanations, three executed examples, a flowchart, self-check
quiz and answer key, existing notes/editor; 20 minutes/medium.

| Goal | Draft adaptive v1 | Final adaptive v2 | Actual estimates / observations |
| --- | --- | --- | --- |
| Simple sandwich | 5 stages saved, 18.03s | 4 stages saved, 11.68s, no retry | 2+1+1+1=5 min; grounded foods/no heat, but still splits tomato and cheese into separate tiny stages. |
| Complex study guide | 5 then 6 proposed, rejected, 27.23s | 5 stages saved, 15.17s, no retry | 5+5+5+10+10=35 min, beyond the 20-minute session; first fits. Missing third example/substantive explanation work. |

Draft rejection was `AI_INVALID_OUTPUT` / `duplicate_quest_content`: repeated
literal “Title” fields, including on correction. Nothing persisted for that goal.
Final candidates have distinct titles; both pass implemented schema/essential
checks, but neither is a fully satisfactory complete-goal decomposition under
Codex content inspection. Independent human QA remains pending. More saves and
simple count 4 < complex count 5 are not proof of correct/minimal sizing. Six
stages are supported and tested; the final complex live example chose five.

Actual final simple stages: Prepare the bread → Add the tomato → Add the cheese
→ Assemble the sandwich. Action: “Combine the bread layers with the tomato and
cheese, then serve immediately.” Criterion: “No-cook sandwich is assembled and
ready to serve.” Unnecessary knife/spoon suggestions and minute-scale splitting
remain quality caveats; no cloud or shopping prerequisite is added.

Actual final complex stages: Outline the Structure of the Study Guide → Write
and Run the First Example → Write and Run the Second Example → Draw a Flowchart
→ Create a Self-Check Quiz and Answer Key. One action: “Write a `while` loop that
counts from 1 to 5 and prints each number. Run the code to verify the output.”
The model omits the requested third executed example and gives only an outline
for explanations. Existing literal checks do not universally detect omissions;
the stage-count enhancement does not claim to solve that broader quality limit.

Final mean/median full-workflow latency 13.42s, maximum 15.17s; 2/2 structurally
valid, 2/2 saved, 0 corrections/timeouts. Draft was 1/2 saved with one correction.
All outputs/counts/timings preserved separately:
[draft](benchmarks/linux-adaptive-sizing-qwen3.json),
[final v2](benchmarks/linux-adaptive-sizing-qwen3-v2.json).
Native counts are recorded even when proposal validation fails; Codex inspection
is separate from blank human-QA fields. No private production inputs were used.

Reproduce from backend/ with installed dependencies/model and a new output path:

```bash
python -m app.benchmark_pipeline --sizing-cases --model qwen3:1.7b --url http://127.0.0.1:11434 --capture-native --machine-label "James Windows demo laptop (when actually run there)" --output ../docs/benchmarks/windows-adaptive-sizing.json
```

Verification: 154 backend tests passed (13 sizing/migration tests plus the prior
141), including all 2–6 bounds, whole-goal duration, XP/idempotent completion,
current-only privacy, restart, replan slots/history, exact v2→v3 row preservation,
rollback after DROP, FK restoration and retained legacy histories over six.
An initial regression run failed because an old fixture expected two quests to
be invalid; it was corrected to the new one/seven bounds and the full suite rerun.
Schema v3 rebuilds only plan_versions count checks; no permanent tables added.

Frontend typecheck/build and 12 unit tests passed. `node tests/core-flow.mjs`
passed 18 browser scenarios: the prior 16 plus two/six-stage campaigns with real
API/temporary SQLite and **mocked Ollama count selection**. They exercise three
temporary checkpoints, no hidden content, sequential unlocking, duplicate XP
protection, campaign XP and completed refresh. Browser evidence:
`/tmp/quest-phase4b-p5wDRe`. These are separate from live CLI inference. No Windows,
disconnected-internet or human task execution claim. Dependency/compilation,
documentation-link and diff checks passed.

**PARTIAL overall:** backend count support and variable Campaign Map are verified;
minimal/useful AI sizing remains unproven and complete-goal coverage is uneven.
No more inference/tuning was performed after this two-revision probe. No PRD,
default model, inference budgets, checkpoint persistence, XP algorithm, UI redesign,
commit or push. Stopped for review.
