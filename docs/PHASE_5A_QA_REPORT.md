# Phase 5A — End-to-End QA and Integration Testing

**Later Windows follow-up:** this report records the original Linux QA run.
The user's subsequent Windows setup, AI-quality QA and offline service-restart
confirmations are tracked in [demo readiness](DEMO_READINESS.md). Frontend
replanning was later authorized and integrated; its current behavior is documented
in [the frontend plan](FRONTEND_PLAN.md#user-facing-replanning). Historical FAIL/
NOT TESTED entries below are preserved rather than retroactively marked passed.

**Final status: PARTIAL.** State integrity and tested integration flows passed.
The user-facing replan flow is missing, and real-model content still needs review.
Successful persistence is not proof of semantic usefulness or release readiness.

## A. Environment and model tested

Executed October 10, 2026 (Philippine time), on Matthew's Linux development laptop,
not James's Windows demo machine. Git checkpoint: `aa9552e2c119b40eb236799eeec64cd8f73cce8e`,
with pre-existing uncommitted Phase 3/4 work preserved. Tests use synthetic inputs.

- Linux `7.2.5-3-omarchy`, x86_64; AMD A10-7860K CPU.
- Detected RAM: 15,640,678,400 bytes (about 14.57 GiB).
- Detected GPUs: Radeon R7 integrated graphics and NVIDIA GTX 1050 Ti, 4096 MiB.
- Python 3.14.7, FastAPI 0.143.0, SQLAlchemy 2.0.54, Uvicorn 0.54.0,
  Pydantic 2.14.0, HTTPX 0.28.1.
- Node 26.7.0, npm 12.1.0, Chromium 152.0.7977.82.
- Ollama 0.40.2 at `http://127.0.0.1:11434`; installed tag `qwen3:1.7b`,
  GGUF Q4_K_M, digest `8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`.
  Runtime metadata reports parameter_size `2.0B`; this records the installed
  artifact's metadata, not a verified model-provenance claim. No model was changed,
  pulled or automatically switched. Backup-model inference was not tested here.
- Prompt `adaptive-stages-encouragement-v1`, quality policy `essential-constraints-v3d.1`;
  temperature 0, seed 42, num_ctx 4096, num_predict 1600, think=false.
  Connect <=3 s, each generation <=60 s, whole generation <=120 s,
  maximum two proposal attempts, no mandatory semantic-review call.

**Database protection:** regular repository configuration resolves to
`backend/app.db`, which exists. No QA command opened, migrated, reset or exercised
that user database; therefore no user-data backup/copy was required or made.
Every backend test uses its own temporary database. The real-model CLI creates a
fresh temporary SQLite database and removes it only after disposing its own engine.
The final browser run used `/tmp/quest-phase4b-S7K8AG/state.db` (schema v4), served by
an owned FastAPI process on 127.0.0.1:8004, React production preview on localhost:4184,
and isolated Chromium on port 9229. Only that test backend was stopped/restarted.
Other running backends may have configuration overrides; none was used by these tests.

Evidence:
[real-model data](benchmarks/linux-phase5a-qwen3.json),
[browser results](benchmarks/linux-phase5a-browser.json).
Only fictional goals/model content appear in these files. Local screenshots and
the isolated browser DB remain in `/tmp/quest-phase4b-S7K8AG/`.

## B. Test matrix

PASS/FAIL refer to the specific check below, not the whole release.

| Check | Result | Evidence / boundary |
| --- | --- | --- |
| A: simple two-stage campaign, explicit completion, encouragement, duplicate XP, final refresh | PASS | Real React/FastAPI/SQLite; mocked Ollama household plan |
| B: six-stage campaign, every-stage XP/level/encouragement, midway/final refresh | PASS | Real stack; mocked study plan; 80 campaign XP |
| C: complete one, pause, browser refresh, resume same quest | PASS | Same current ID, immutable history and XP |
| D: backend replan, cap, preservation, stale/replayed request, frontend restoration | PASS | API-initiated replan, real engine; mocked replacement generation |
| D: replan initiated by a normal frontend user | FAIL | No replan form/control/API adapter in dashboard; test does not fabricate one |
| E: unavailable model, invalid JSON, timeout, hard quality rejection | PASS | MockTransport injects upstream failures; actual API/persistence/UI recovery |
| E: backend unavailable before completion, restart same DB, retry | PASS | Owned test FastAPI actually stopped; no premature XP or celebration |
| E: lost completion response / duplicate request | PASS | Real committed transition, response dropped, safe replay returns zero XP |
| E: refresh after commit before UI confirmation | PASS | Browser reload injected before delivering real completion response |
| E: completion with Ollama unavailable | PASS | Runtime failure simulated; no completion-time model call |
| F: unnamed presentation topic -> one focused question -> retained answer -> grounded save | PASS | Deterministic real check-in policy; mocked plan after answer |
| Required schema/XP/constraints, concurrency, rollback, migration/reopening | PASS | 163 backend tests, temporary SQLite |
| Locked/superseded data protection and private browser storage | PASS | Actual public DTO/DOM checks plus backend protection tests |
| Real Qwen3 household/study/complex/low-energy plans structurally valid and saved | PASS | 4/4 operations, all first attempt |
| Real Qwen3 complex guide fully covers requested deliverables | FAIL | Explicit explanatory-writing step absent; sections alone do not establish coverage |
| Real Qwen3 no-cook wording consistently grounded | FAIL | Diagnostic candidate contains “even cooking” despite no-cook context |
| Real Qwen3 -> actual HTTP/API -> React -> completion/refresh | PASS | Separate live snack run, three stages, 40 campaign XP |
| Disconnected-internet inference | NOT TESTED | Reserved for later Phase 5; no offline claim |
| Windows demo machine | NOT TESTED | Reserved for James's machine; no Windows-readiness claim |
| Independent human content review / physical task execution | NOT TESTED | Codex inspection and synthetic explicit UI completion only |

## C. Two-stage campaign walkthrough

Mocked goal: “Clean my desk before studying using the storage and notes already
beside it.” Capacity 15 minutes, low energy. Actual production API creates two
quests: Clear the desk (easy, 10 XP) and Set up the study space (easy, 10 XP).
Only the first title/action is initially returned/rendered; one neutral locked
placeholder occupies the second position. Active encouragement is null; locked
content never enters the public response or DOM.

The test stops its FastAPI server before the first completion. React reports
Cannot reach FastAPI, with no success/celebration. Restarting the same database
restores the identical active questline and profile; Retry previous action commits
one completion, displays its own message and reveals Stage 2. A repeated completion
returns already_completed/0 with the same encouragement.

Final completion runs during a simulated Ollama outage. The harness reloads the
browser immediately after the DB commits, before React receives confirmation.
Both history/messages, completed status and 20 campaign XP restore; no celebration
is incorrectly replayed on refresh. Lifetime profile moves 130 ->150 (Level 2).
The test does not claim a person physically cleaned a desk.

## D. Six-stage campaign walkthrough

Mocked goal: study Python for/while loops using existing notes and installation;
60 minutes, medium energy. The six meaningful fixtures are Read the loop notes,
Run a for loop, Run a while loop, Compare the loop results, Check a boundary case,
and Test the loop knowledge. Initial response/DOM exposes only Stage 1 and five
anonymous locked placeholders.

Stages complete through actual React controls. After every completion the test
checks exact message, backend-awarded reward, current pointer/order, history count,
locked-placeholder count, profile XP and backend-derived level displayed in the
header. Reward sequence is 10,10,10,20,20,10: 80 campaign XP. Lifetime profile moves
150 ->230; its backend level crosses 2 ->3. No frontend XP award is performed.

Pause/reload/resume after Stage 1 preserves the current Stage 2 ID, completed
record/message and XP. After three completions a separate browser refresh
restores Stage 4 and identical saved state. Final refresh restores all six
completed stages/messages, no current/locked stage and completed status.
These fixtures test six-stage support, not model count-selection reliability.

## E. Pause/resume and replanning results

Pause/resume PASS after earned progress and a refresh. Completion is disabled while
paused; resume restores the same current quest with no penalty. The real backend
restart in scenario A also verifies application DB initialization/reopening.

Replanning is tested through its **existing HTTP endpoint**, because there is no
frontend replan control. After completing Read the loop notes in a new six-stage
line, a deliberately invalid six-replacement response exceeds the five remaining
slots. Two bounded schema attempts end in 502 AI_INVALID_OUTPUT; the original
questline, complete history and profile remain identical.

A valid five-replacement response then commits plan version 2 with one completed
plus five new stages (six total). Completed ID/content/timestamp/encouragement/XP
stay unchanged; old unfinished rows are superseded internally. Same-key replay
returns identical public state without creating version 3; a new stale-revision
request returns 409 STALE_REVISION. Browser reload shows only the current replacement,
completed history and anonymous future placeholders; the original superseded title
is not exposed as a quest. Lifetime profile stays 240 XP/Level 3 during replan.

Backend regressions separately cover the one-remaining-stage case, stale/racing
replans, transaction failure rollback, superseded completion protection and legacy
histories. **API success does not substitute for an implemented user-facing replan
flow.** That missing control remains a release gap, outside this no-feature QA scope.

## F. Failure recovery and clarification

The existing 20 browser regressions plus five Phase 5A cases exercise actual HTTP
contracts, no-store reads, serialized UI mutations, UUID/revision/idempotency
values, non-JSON sanitization, 409/Retry-After handling, lost generation responses,
API 404s, stale state refetch, abandoned reads and malformed DTO rejection.

Mocked Ollama connection failure, timeout, malformed JSON and essential-quality
rejection retain the saved check-in, save no partial plan and award no XP. Explicit
retry uses the same unchanged intent. Lost committed completion recovers by quest
ID with zero additional XP; the celebration never appears before confirmation.
Actual stopped-backend completion and immediate committed-response refresh are
covered by the new household test. Saved reads/completion/pause/resume work when
inference is simulated unavailable. These are controlled failures, not observed
unplanned production outages or internet-disconnection tests.

For “I need to present a complex topic that I know nothing about.” the actual server
asks exactly: “What is the presentation topic and the main result you need to
communicate?” No generation precedes the answer. The fictional answer supplies an
AI introduction for classmates, existing local notes, three slides and one timed
five-minute rehearsal. Original goal and answer persist, revision becomes 2,
question becomes null and refresh restores the ready check-in. The subsequent
mocked plan covers that supplied topic/count/rehearsal. This verifies grounding
transport/policy, not universal live-model relevance.

## G. Real-model outputs and semantic assessment

The four requested diagnostic cases each ran once through the **actual production
check-in/generation/persistence services** and local Ollama, with temporary SQLite.
They are not React/browser runs. The additional live browser run below separately
exercises React -> actual FastAPI -> Ollama -> SQLite -> completion/refresh.
No prompts, default model or gates were tuned for QA. Diagnostics are local and
fictional; production logs do not print these inputs.

| Case | Capacity | Clarification | Stages | Latency | Saved / attempts | Codex inspection, not human QA |
| --- | --- | --- | --- | --- | --- | --- |
| A | 15 min / low | None | 2 | 12.89 s | Yes / 1 | Usable desk-tidying plan; subjective “organized/ready” criterion and medium effort deserve review. |
| B | 30 min / medium | None | 2 | 8.46 s | Yes / 1 | Usable narrow starting practice; not comprehensive exam preparation. “Control statements” title actually leads to conditionals. |
| C | 20 min / medium | None | 4 | 12.99 s | Yes / 1 | PARTIAL: outline names explanation sections but no action explicitly writes for/while explanations; optional unverified software suggestions and subjective criteria. |
| D | 10 min / low | None | 2 | 7.41 s | Yes / 1 | PARTIAL: uses supplied foods, no explicit stove/shopping step; “even cooking” rationale contradicts no-cook framing and “cut ... using hands” is awkward. |

Structural success and persisted-plan rate: **4/4 (100%)**, all first attempt;
zero corrections, timeouts or essential-gate rejections. Median 10.67 s, mean
10.44 s, max 12.99 s. No useful-output reliability rate is inferred from four samples.
Codex rated two starting plans usable with caveats and two partial; independent
human review is pending. These different inputs are not a paired comparison with
Phase 3D. Backend regressions ran concurrently, so these timings are observed
application latencies, not isolated hardware performance measurements. Ollama
reported no resident models before the run; first loading cost may be included.

All validated optional encouragement fields were null: completion falls back
safely rather than rejecting the plans. Inspect the native outputs in the JSON for
unfiltered fictional candidate content. Warnings were advisory, not hidden gates.

### Exact inputs and generated actions

#### Case A

Goal: Clean my desk before studying.

Context: 15 minutes, low energy; deadline and notes null; no clarification.

1. **Clear the desk of unnecessary items** (5 min, easy): Remove all items not needed for studying from the desk, ensuring only relevant materials remain.
2. **Organize the remaining items** (5 min, medium): Arrange the remaining study materials in a logical, organized manner on the desk.

Rejection/correction: none. Advisory codes: unobservable_criteria.

#### Case B

Goal: Study Python loops for tomorrow's quiz.

Context: 30 minutes, medium energy; deadline and notes null; no clarification.

1. **Write a simple loop to print numbers from 1 to 10** (5 min, easy): Use Python to create a loop that prints numbers from 1 to 10, ensuring each number is on a new line.
2. **Practice loop control statements** (5 min, medium): Add an if statement to check if a number is even or odd, and print a message accordingly.

Rejection/correction: none. Advisory codes: none.

#### Case C

Goal: Create a local study guide for Python loops: explain for and while loops, write and run three examples, draw a flowchart, and finish with a self-check quiz and answer key using my existing notes and Python editor.

Context: 20 minutes, medium energy; deadline and notes null; no clarification.

1. **Outline the structure of the study guide** (5 min, easy): Organize the content into sections: introduction, explanation of for and while loops, examples, flowchart, quiz, and answer key.
2. **Write and run three Python loop examples** (8 min, medium): Use Python editor to write and run three examples: 1. for loop with range, 2. while loop with counter, 3. nested loop for matrix.
3. **Draw a flowchart of the loops** (6 min, medium): Create a flowchart using a tool like Microsoft PowerPoint or draw.io to visually represent the loop structure.
4. **Create a self-check quiz and answer key** (7 min, medium): Design a quiz with multiple-choice questions on for and while loops, and provide an answer key.

Rejection/correction: none. Advisory codes: optional_tool_suggestion, unobservable_criteria.

#### Case D

Goal: Make a no-cook vegetarian snack using only bread, tomato and cheese; no stove and no shopping

Context: 10 minutes, low energy; deadline and notes null; no clarification.

1. **Prepare the base** (2 min, easy): Cut a loaf of bread into small pieces using hands, ensuring even size for even cooking.
2. **Assemble the snack** (2 min, medium): Layer bread, tomato, and cheese in a bowl, pressing gently to hold the ingredients in place.

Rejection/correction: none. Advisory codes: none.

### Separate real-model browser journey

The same constrained snack goal was used once more specifically to verify the
live HTTP/browser path, not to inflate the four-case validity rate. React generated
and saved **3 stages in 16.503 seconds**,
then explicitly completed all of them, with encouragement/next-stage transitions.
Lifetime XP moved 240 ->280
(Level 3), for **40 campaign XP**. Final browser refresh
restored completed status, history and messages. During completion the fixture
simulated Ollama connection failure; the real Ollama process itself was not stopped.
No physical snack preparation or verified criteria execution is claimed.

Generated actions (revealed sequentially after confirmed progression):

- **Prepare the base** (2 min, 10 backend XP): Cut a loaf of bread into small pieces using hands, then arrange them in a bowl.
- **Add ingredients** (1 min, 10 backend XP): Place a slice of cheese and a slice of tomato onto the bread in the bowl, ensuring they are evenly spaced.
- **Assemble the snack** (1 min, 20 backend XP): Gently press the cheese and tomato onto the bread in the bowl, forming a compact snack shape.

Codex inspection: no new ingredient/stove/shopping requirement, but hand-cutting
wording is awkward and the small assembly outcome is split into potentially
redundant add/press stages. A live saved campaign proves integration; it does not
prove optimal sizing, general semantic safety or an independently useful recipe.

## H. Automated test counts and reproduction

| Command (working directory) | Actual result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -v` (`backend/`) | PASS: 163/163, 48.111 s; all existing regressions retained |
| `npm run typecheck` (`frontend/`) | PASS |
| `npm run build` (`frontend/`) | PASS, also reruns typecheck; 113 modules transformed |
| `node --test --test-isolation=none tests/validation.test.mjs tests/campaign.test.mjs` (`frontend/`) | PASS: 14/14 |
| `node tests/core-flow.mjs --phase5a --live-campaign` (`frontend/`) | PASS: 25 mocked-model cases + one live-model case |
| `.venv/bin/python -m pip check` (`backend/`) | PASS: no broken requirements; sandbox cache-warning only |
| `.venv/bin/python -m compileall -q app tests` (`backend/`) | PASS |
| `git diff --check` | PASS |

Backend tests cover count/duration validation, single-current rules, atomic
completion/rewards/unlocking, duplicate/concurrent completion, XP levels, foreign
keys, busy/unavailable storage, write/commit rollback, stale/racing replan,
immutable completed history, hidden/superseded filtering, check-in/intent recovery,
JSON/timeout/retry handling, guarded v1/v2/v3->v4 migrations and file/process restart.
Frontend tests validate DTO privacy, shape/state/reward errors, counts/checkpoints,
campaign/profile progress distinction and legacy encouragement fallback.

A final read-only inspection of the isolated browser database confirmed schema
v4, SQLite `integrity_check=ok`, no `foreign_key_check` violations, 24 unique
completion records, profile XP=ledger XP=280, and zero questlines violating the
single-current count rule. This inspection did not open the user database.

Reproduce four real cases from `backend/` (choose a **new** output filename):

```bash
.venv/bin/python -u -m app.benchmark_pipeline --qa-cases --capture-native \
  --model qwen3:1.7b \
  --machine-label 'Matthew Linux development machine; not Windows/offline verification' \
  --output /tmp/phase5a-real-model-new.json
```

PowerShell equivalent uses `.\.venv\Scripts\python.exe` and a new output file in
`$env:TEMP`; run in backend/. This command is provided, not tested on Windows.
CLI refuses an existing output filename and uses a temporary database. It adds
no model download, classifier, automatic replan or production endpoint.

From `frontend/`, after building:

```bash
node tests/core-flow.mjs --phase5a
node tests/core-flow.mjs --phase5a --live-campaign
```

The second command adds one real local snack generation to the deterministic suite.
Chromium, the existing backend virtual environment and unoccupied test ports
8004/4184/9229 are required. The harness refuses occupied ports and cleans up only
its own processes. Network/native-browser runs needed approved execution outside
the sandbox. After the tool-server interruption the completed model/backend logs
were inspected; those runs were **not** repeated. A first 24-case browser pass was
followed by the final 25-case run after adding the missing presentation test. The
build was rerun because the interrupted tool session no longer had its result.

Final local logs: `/tmp/phase5a-backend-tests.log`,
`/tmp/phase5a-frontend-build.log`, `/tmp/phase5a-real-model.log`,
`/tmp/phase5a-browser-final.log`. Permanent JSON evidence is linked above.

## I. Bugs found and fixes applied

No release-blocking state-engine, migration, XP, privacy, completion or
pause/resume defect was reproduced. Therefore **no production behavior was changed**.

Confirmed gaps/findings:

1. Missing frontend replan workflow: API adapter/control/form absent. Recorded as
   FAIL for normal user journey, not masked by an API-only test or implemented as
   a new QA-phase feature.
2. Real complex-guide completeness and no-cook wording issues: recorded above;
   no prompt tuning, increased retries, fabricated fallback or weakened acceptance
   assertions was applied. Broader model suitability remains PARTIAL.
3. Existing browser coverage lacked actual test-backend stop/restart before a
   completion, reload before receipt delivery, paused refresh after earned progress,
   every-stage six-plan encouragement/level checks, API replan cap/failure/replay UI
   restoration and a presentation-topic clarification journey. Added focused
   fixtures/assertions using the existing runner; existing tests remain intact.
4. Harness previously wrote results only on full success. It now saves completed
   cases and a FAIL entry on exception, preserving evidence for interrupted/failed
   runs. This is a test-runner fix, not application error masking.

Files changed in this phase:

- `backend/app/benchmark_pipeline.py`: developer-only four-case QA selection;
  bounded production service/adapter reuse, no automatic extra replan.
- `frontend/tests/backend_fixture.py`: coherent household/study/replan/presentation
  synthetic plans for missing end-to-end coverage.
- `frontend/tests/core-flow.mjs`: new Phase 5A scenarios, owned backend restart,
  immediate post-commit reload, failure-evidence preservation.
- `docs/benchmarks/linux-phase5a-qwen3.json`: actual fictional native-model evidence.
- `docs/benchmarks/linux-phase5a-browser.json`: actual browser results.
- `docs/PHASE_5A_QA_REPORT.md`: this report.

## J. Remaining release blockers

- Full adaptive P0 browser workflow cannot be demonstrated until a user can
  initiate replan from the frontend. The backend is tested; the missing UI needs
  a separately authorized integration task rather than new feature work here.
- General AI content usefulness/explicit-deliverable coverage remains unproven.
  The saved complex plan demonstrates a coverage gap; the food wording and
  fragmentation need human review. Do not advertise guaranteed relevance,
  expertise, safety or optimal stage count from JSON/persistence success.
- Independent human QA, actual Windows demo-machine validation and true
  internet-disconnected inference are pending. They are not counted as failures
  of these Linux integration tests, nor as readiness evidence.
- Hint/shrink remain unimplemented/deferred; Journey/advanced Progress retain
  foundations. This phase did not invent those features or certify full PRD completion.

## K. Final status

**PARTIAL.** All executed automated integration/state checks passed, including one
live model-generated campaign saved/completed through React, but complete P0
release readiness is blocked by the frontend adaptive-flow gap and limited
semantic-quality evidence. No real user campaigns were used; no application
feature, database schema, XP engine, default model or finalized PRD was changed.
No commit or push. Stop after Phase 5A for review.
