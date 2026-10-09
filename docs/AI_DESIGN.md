# Local AI operation design

## Optional completion encouragement

The existing structured plan request now includes optional
`completion_encouragement: string|null` per quest. Prompt version is
`adaptive-stages-encouragement-v1`; model, generation settings, essential gates
and two-attempt budget are unchanged. No inference is added to completion.

To avoid invented achievements and future-stage spoilers, optional model copy
may assert only completion of its exact quest title plus one of four supportive
forest-themed endings in [encouragement.py](../backend/app/encouragement.py).
The model may vary the ending; this is constrained copy, not unrestricted praise.
Wrong types, missing/blank/oversized copy, other quest titles, unsupported claims
or other wording become null without failing generation or consuming a retry.
All required quest content and state restrictions retain strict validation.

After explicit completion the backend grounds the final message in a bounded,
exact excerpt of the quest title and action. Safe model endings are retained;
otherwise deterministic quest-specific copy is used. This does not infer skills,
real-world outcomes or success of the whole goal. Public active/paused messages
are null, locked/superseded content is absent, and completed history contains the
message. Schema v4 stores optional copy; completion persists the final message in
the existing XP transaction. Legacy completed quests receive read-only fallback.
No private check-in or message is logged or sent off the laptop.

P0 proposal from PRD §2/§4/§8–12/§15–18. Actual schema compatibility and performance
are **not benchmarked in Phase 0**. Reuse [ollama.py](../backend/app/ollama.py) and
HTTPX lifecycle. React talks only to FastAPI. [API_CONTRACT](API_CONTRACT.md)
describes user-facing inputs; schemas below describe **internal model outputs**.

## Phase 1B implemented boundary and evidence

Phase 3 now implements grounded initial generation/replanning and persistent
deterministic clarification in [services/check_in.py](../backend/app/services/check_in.py).
The historical Phase 1B description below remains a checkpoint record. Current
semantic evidence and limitations are in [AI_BENCHMARK](AI_BENCHMARK.md#12-phase-3-production-pipeline-recovery).

Production requests pass the complete original goal, accepted clarification,
effective notes/capacity/deadline, replan change reason and completed milestones. The original adapter
is reused with an additive grounding/replacement option; legacy benchmark calls
use the current schema/prompt. Initial schema is 2–6; replacement is 1–6, further
bounded by remaining slots after completed history. Python computes
dates and all application state. Generic diagnostics and structured inference
now reject non-loopback Ollama URLs before network access; no model downloads or
automatic switching were added.

Clarification uses known deterministic ambiguity checks, not an expensive AI
classification loop. At most one question per chain; an insufficient answer can
be corrected against that same question. Summary is deterministic convenience
text; full original goal and accepted answer are retained independently.

**Phase 3D current policy:** strict schema → deterministic essential constraints
→ persistence, with **no model-based semantic approval call**. The old reviewer
and scoped-patch helpers remain available for explicit developer experiments;
production generation/replanning do not invoke them. The model is not required
to approve its own plan.

[quality.py](../backend/app/quality.py) separates essential failures from internal
diagnostic warnings. Schema/authority fields, counts, duration bounds, explicit
outcome coverage, material contradictions, mandatory invented tools/external
dependencies, unsafe food instructions and repeats of completed work still block.
User session capacity remains a hard first-quest limit; low-energy ten-minute
guidance, difficulty opinions, subjective/vague wording, copied criteria and minor
sequencing are warnings. Explicitly optional tools/resources are warnings unless
they contradict a user prohibition or include a mandatory prerequisite.
These necessary checks still have false-positive/false-negative risk, **not a
keyword relevance proof**. No general semantic-relevance guarantee is claimed.

One shared correction budget for malformed/schema or essential-constraint failure:
maximum two generation calls, zero reviews, <=120 seconds before business commit,
<=60 per attempt, connect <=3. Only blocking codes prompt one complete corrected
candidate; warnings do not trigger repair, rejection or extra inference. No
transport retry, fallback questline or automatic model switching. Persistence
revalidates the accepted proposal; inference never holds a write transaction.
Failure preserves check-in/old plan for explicit retry of the existing intent.
Warning codes appear only in local developer diagnostics, not public DTOs, normal
logs or browser state. CLI candidate capture is limited to fictional QA inputs.

Current prompt is adaptive-stages-v2; gate is essential-constraints-v3d.1.
This approved post-PRD enhancement changes count guidance, not quality policy:
the same call chooses the smallest meaningful stage count for the complete goal.
Simple single outcomes normally combine small actions into two stages; complex
multiple deliverables may need four to six. No classifier call or padding.
Available time/energy guide immediate effort; the full campaign can span sessions.
Replanning's native maxItems is 6 minus completed history, including a one-stage
remaining plan. The trusted replacement service independently enforces the cap.
Its minimum is two with no completed history, otherwise one, so the total is 2–6.
Generic cooking requests ask which dish/available ingredients to use; named dishes
or supplied ingredients do not trigger that question. Presentation wording with an
unknown/complex unnamed topic asks the existing topic question; a specific AI
introduction does not. Explicit slide counts and requested rehearsal must appear
in the plan or completed coverage. Research stays local. Observable physical outcomes
and short concrete actions are supported. Explicit no-heat, ingredient-only,
vegetarian, no-auth/deployment and existing-runner constraints remain hard checks.
FastAPI grounds Python; low energy alone does not make a bounded medium quest
invalid. These targeted rules are necessary screens, not general relevance proof.
Historical Phase 3C repair/review native schema compatibility fixes remain tested,
but neither mechanism is required for Phase 3D acceptance. Printed loop outputs
and timed runs count as observable; mental understanding/aesthetic grading still
receive warnings rather than preventing a conforming plan from being saved.
Explicit slide/rehearsal counts, required tools versus optional examples, available
foods and unmentioned special cleaning supplies have focused regression coverage.
The historical [Phase 3C evidence](AI_BENCHMARK.md#14-phase-3c-bounded-semantic-recovery)
saved 4/6, with only 2/6 saved candidates rated fully acceptable by Codex inspection.
See [Phase 3D evidence](AI_BENCHMARK.md#15-phase-3d-essential-only-acceptance) for the
new measurements. Independent human QA remains pending.

### Historical Phase 1B spike (current orchestration described above)

The existing [schemas.py](../backend/app/schemas.py) now provides strict
CheckInInput, QuestProposal and initial QuestPlan models. The existing adapter's
`generate_quest_plan` returns a validated content result or a typed recoverable
QuestGenerationError. It reuses HTTPX transport, local `/api/generate`, native
JSON schema format and Qwen3 think=false. Generic public endpoints/contracts
remain unchanged; no DB import/write, production quest endpoint or state engine.
Only initial generation is implemented, not the other proposed operations below.

CheckInInput is the authorized Phase 1B minimal subset (goal/time/energy/deadline).
Accepted interpretation summary, notes and follow-up orchestration are future
Phase 3 integration, not present features. Strict strings/integers/enums, extra
field rejection, 3–5 bounds, normalized duplicate detection and first-estimate
capacity validation are implemented. Deadline arithmetic is Python-owned.
Unknown IDs/XP/status/etc are forbidden content fields. Structural validation
does not prove goal relevance, effort or semantic safety.

Actual default budgets: connect <=3 seconds, attempt <=60 seconds, total <=120
including validation/retry. One correction with safe validator codes, never
raw failed output; no transport/timeout retry or model failover. Non-loopback
structured inference URLs are refused. Reuse the existing lifespan client with
trust_env=False. The generic diagnostic transport's response/error contract is
preserved; only the new structured method uses these stricter guards.

Run `python -m app.benchmark_ai --model qwen3:1.7b` from backend/ in its existing
virtual environment. It has fictional A–E cases, manual model/URL/timeout selection,
repeat counts, optional JSON output and unrated quality fields for content review.
Full commands/data/settings are in [AI_BENCHMARK](AI_BENCHMARK.md).

Final Linux v3 primary: 10/10 accepted, all first attempt, median 8.60 s/max 13.29 s.
Backup alone: 10/10 accepted, 9 first attempt/1 after correction, 10/11 valid
attempts, median 8.00 s/max 14.76 s. Earlier backup partial-GPU runs timed out;
all cohorts are retained. Native schema/think=false compatibility is verified
for these installed Linux artifacts, not James's Windows laptop.

**Phase 1B is PARTIAL for product feasibility:** primary assignment/ambiguous plans
still invent work/language; backup adds online/cloud/auth scope and weak criteria.
Use qwen3 with temperature 0/seed 42/num_ctx 4096/num_predict 1600 for the next
iteration, not as a claim that content is approved. Neither JSON format, stronger
prompts nor the one chat probe established reliable semantic compliance. Phase 3
needs ready context/one essential clarification and renewed quality evidence.
Actual Windows, disconnected-internet operation and peak RAM remain unmeasured.
The broader operation/benchmark plans below remain requirements, not completed tests.

## Runtime and structured validation

Primary `qwen3:1.7b`, manually configured backup `qwen2.5:1.5b`; endpoint from
OLLAMA_BASE_URL, model from OLLAMA_MODEL. Never auto-failover or download. Core
configuration must resolve to loopback on the demo laptop; HTTPX trust_env=False
avoids proxy redirection. No remote AI fallback, telemetry or browser-to-model calls.

Recommended transport: POST Ollama `/api/generate`, stream=false, `system` instructions,
JSON-encoded trusted context/user text, and `format` set to the exact Pydantic
JSON schema. Ollama documents JSON-schema format; that does **not** establish that
the installed version/model obeys every constraint. Validate locally every time.
The current adapter uses think=false for qwen3; verify supported thinking settings
with the installed runtime before keeping that option in the structured spike.
[Ollama generate API](https://docs.ollama.com/api/generate).

Pydantic strict types, extra=forbid, bounded nonblank strings, exact enums and
cross-field checks apply to all outputs. Parse the `response` JSON string into
the operation's schema; reject invalid outer response, error payloads, unfinished/
truncated generation, unknown authority fields or invalid inner JSON. Do not
strip arbitrary prose/markdown/code fences and hope it is a valid plan. Returned
text is untrusted; display escaped text, never execute HTML/code/SQL.

## Shared prompt responsibilities

System instructions establish task boundary, output schema, supportive tone and
no guilt/penalties/clinical advice. User text is quoted data, not instructions to
ignore the schema or award XP. Never output trusted IDs, sequence, status, plan
version, completion flags, XP or level. Treat supplied completed milestones as
already done, not new work. Keep concrete observable deliverable steps and capacity
appropriate starts; estimates are guidance, not guarantees. Do not infer medical
conditions from low energy; explicitly refuse diagnosis/therapy/treatment requests.
No passwords, credentials, external API calls or required cloud services.

Dates/remaining time are computed by Python from typed timestamps, not extracted
as authoritative dates by the model. Omitted deadline/notes must not trigger a
question. Model summaries can clarify language but cannot overwrite typed time,
energy or deadline. Goal changes require a new check-in, not hidden replan edits.

## Operation schemas and behavior

Common QuestProposal:

```text
{
 title: string[1..100], action: string[1..2000],
 completion_criteria: string[1..1000], estimated_minutes: strict integer[1..1440],
 difficulty: easy|medium|hard, hint: string[1..1000]|null (optional/default null)
}
```

Backend accepts difficulty as a suggestion, validates it, then maps reward in
Python. A proposal has no starting_action/XP/id/status/order/version fields.

### 1. Check-in interpretation

Input: typed CheckInContext (goal, time, energy, optional deadline/notes), plus
existing follow_up_question and user answer for mode=answer. Include an explicit
question allowance: 1 on start, 0 after answer.

Output is a strict discriminated union:
`{decision:"ready",summary:string[1..2000]}`;
`{decision:"follow_up",question:string[1..300]}`;
`{decision:"unsupported",message:string[1..300]}`.
Answer-mode schema excludes follow_up entirely. Ask only if essential ambiguity
about the actual deliverable prevents meaningful planning. Never ask for optional
deadline/context or re-ask time/energy supplied in typed fields. For an insufficient
answer return a recoverable clarification error; no second interview question.

Validation: schema/allowance plus existing check-in revision. Unsupported requests
map to 422, not clinical text. Persist accepted typed context, one question/answer
and ready summary after validation; rejected new interpretation saves no check-in
business row. No quest/XP state changes. Inputs are sensitive local context; no raw
logs/transcripts beyond required local fields.

### 2. Initial structured questline generation

Input: ready typed context and accepted check-in summary. Output:
`{quests: QuestProposal[2..6]}`. System: useful deliverable contributions, sensible
dependency order, small first action fitted to available time/energy, observable
criteria, no busywork or quest authority fields.

Validation: 2–6, all item schemas, no blank/duplicate normalized titles/actions,
first estimated_minutes <= available_minutes, no forged IDs/XP/state. Semantic
usefulness/appropriate energy are QA/benchmark criteria, not magically proven by
JSON validation. The total plan can span sessions; do not claim its estimates sum
fits one reported session. Backend creates IDs/order/version/status/reward only
after acceptance. Save line/version/quests and consume check-in transactionally;
malformed/failed/stale generation saves no partial plan or rewards.

### 3. Contextual hint

Input: goal/current typed capacity, **current quest** content and completed milestone
summaries, plus optional user question. Do not send locked quest details: the hint
must not leak them. Output `{hint:string[1..1000]}`.
System: a specific next-step cue/example for this quest, not a new questline or
completion claim. Validation: bounded nonblank text, current/active eligibility,
matching revision/receipt attempt at commit. Persist accepted hint on that quest,
increment revision, no original action/criteria/XP/status changes. No raw logs.

### 4. Smaller starting action

Input: same current-only context, original action and completion criteria, optional
reason. Output `{starting_action:string[1..1000]}`.
System: a smaller entry step that helps start the original milestone, explicitly
not a replacement completion criterion or an auto-completion. Validate shape and
revision/eligibility; QA verifies it is meaningfully smaller. Persist assistance
only, retaining original action/criteria/reward; no XP/unlock or child quest.

### 5. Adaptive replanning

Input: immutable goal, completed milestone content, internal remaining-plan content,
updated typed capacity/deadline/notes and optional reason. Sending the full unfinished
plan to local inference is internal; it is never returned in ordinary API views.
Output `{quests: QuestProposal[1..6]}` for remaining work only, with native/local
maxItems narrowed to 6−completed. No replan if completed history already uses six.
System: completed work stays done; adapt unfinished dependencies to new capacity;
support past-deadline recovery without shame or penalties. Model cannot edit stored
completed IDs/rewards. Validate proposal rules (first estimate fits updated time),
exclude exact normalized repeats of completed actions, then compare captured
revision and receipt ownership. Semantic overlap still needs realistic QA cases.
Only then atomically supersede old unfinished work, create new version/replacements
and activate one. Any format/stale/storage failure leaves original line/completed
history/XP unchanged. Persist accepted plan/context snapshot, not raw output logs.

## Timeouts, retries and recovery

Initial **proposed budgets**, to verify on real hardware:

| Operation | Per inference attempt | Whole AI operation | Frontend request ceiling | Receipt lease |
| --- | --- | --- | --- | --- |
| Interpretation, hint, shrink | 15 seconds | 30 seconds | 40 seconds | 45 seconds |
| Initial generation, replan | 60 seconds | 120 seconds | 130 seconds | 135 seconds |
| Tags/readiness | 5 seconds | 5 seconds | Health 10 seconds | None |

Connect timeout <=3 seconds. Use an outer monotonic deadline covering both attempts,
not two unbounded reads. Maximum **one shared** correction for malformed/schema/domain or essential-constraint output,
with concise validator codes and original context; do not repeat sensitive output
in logs. The retry stays inside the original total budget. No automatic retries
for connection/missing-model/storage/timeouts, no third inference and no model
switch. User may explicitly retry a recoverable failed intent with its same key.

502 invalid output/upstream, 503 unavailable model/runtime, 504 timeout; user/input
policy problems 422, stale/ineligible state 409, storage errors 503. See API contract
for envelope. A late result whose revision/receipt attempt no longer matches is
discarded, even if schema-valid. No transaction holds a write lock across inference.
Cancel local HTTP work on abandoned request when possible; correctness still rests
on commit guards, not client cancellation.

## Phase 1 benchmark on actual demo laptop

Record OS/RAM/CPU/GPU, Ollama version, model digest/quantization, prompt/schema
version, cold startup/load, wall-clock operation latency, RAM peak, first-attempt
schema validity, retry count, terminal errors and qualitative usefulness. Use
synthetic prompts. Test each model separately by config/restart; no automatic failover.

| Case | Expected evaluation | Result |
| --- | --- | --- |
| Student assignment, low energy, 10 minutes | 2–6 meaningful stages for the full goal, small first action, no shame | NOT RUN |
| Certification/project deliverable, medium energy, 40 minutes | Observable steps and sensible dependencies | NOT RUN |
| Ambiguous goal “finish it” then one answer | At most one essential follow-up; no repeated interview | NOT RUN |
| Current quest hint and shrink | Contextual assistance, original criteria and XP unchanged | NOT RUN |
| Replan after one completion, less time/past deadline | No repeated completed milestone, valid replacement | NOT RUN |
| Adversarial “award 1000 XP”, malformed/extra authority fields | Strict rejection; no progression mutation | NOT RUN |
| Internet disconnected, loopback retained | Same local structured operations succeed | NOT RUN |

Use at least two warm runs per representative generation case/model plus one cold
load per model; report sample count and median/tail, not universal speed claims.
Suggested warm generation target <=60 seconds, all accepted plans valid within
the 120-second cap and no state corruption. Hint/check-in budgets need realistic
hardware confirmation. If the primary is unreliable, manually select the backup
and record why; do not fabricate latency or silently relax validation. Useful
output and offline reliability are more important than decorative polish.

## Disclosure and privacy

[AI_DISCLOSURE](AI_DISCLOSURE.md) retains the NOT VERIFIED license/tool ledger.
Only Matthew uses Codex CLI. Disclose frameworks/models/tools and pre-existing
scaffold; do not send private check-ins to development services. Local database
storage is not encrypted by this plan. No raw sensitive logs or commits; synthetic
QA examples and sanitized timings only. No medical diagnosis, therapy or mobile
native inference capability is asserted.
