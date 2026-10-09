# Proposed P0 API contract

## Phase 2 implemented subset

Implemented: list/detail/profile, completion, pause and resume with the request,
response, visibility and error rules below. Product errors and input-validation
errors use sanitized `error` envelopes with opaque request IDs; all product
responses use Cache-Control: no-store. UUIDv4 paths/keys, strict positive revision
integers and forbidden extra body fields are validated. CORS now permits
Idempotency-Key. Generic AI diagnostics retain their existing response/detail
contracts. There are no check-in, generation, hint, shrink or replan product routes.

Pause/resume use compact durable transition receipts, not the future general AI
receipt table/leases. Required UUIDv4 keys bind to line/action/body revision and
replay the latest view without reapplying state. No Retry-After exposure is needed
yet because no REQUEST_IN_PROGRESS endpoint is implemented.

Current GET /api/health: 200
`{status:"ok",service:"appbuilders-backend",components:{database:{available:true}}}`;
503 uses status `unavailable` and available=false. Bootstrap occurs at startup,
not GET; health checks that the initialized profile can be read. Ollama readiness
remains GET /api/ai/status, not an inference/combined health check. The full
combined readiness schema below remains proposed and requires future client work.

Internal QuestService interfaces: create_questline(context, validated initial
QuestPlan, summary/model metadata), list_questlines, get_questline, get_profile,
complete_quest, set_paused and replace_unfinished(line_id, expected_revision,
validated ReplacementPlan/context, summary/reason/model metadata). Replacement
is 1–5 proposals; caller supplies effective optional context (future HTTP
orchestration must resolve omitted fields versus explicit null first). No Ollama
call occurs in these methods. Internal creation is not yet check-in-consumption/
creation-idempotency orchestration; replacement is revision-safe but has no public
AI intent receipt. The production creation/replan contracts below are unchanged.

## Complete P0 target contract

**Not implemented in Phase 0.** Based on PRD §6–12; decisions in
[DECISIONS](DECISIONS.md). Current scaffold endpoints and compatibility are in
[ARCHITECTURE](ARCHITECTURE.md). Database entities are internal; never return an
ORM object's full dictionary, full plan, locked IDs or superseded records.

## Shared types and validation

All request bodies use strict Pydantic models with extra fields forbidden, including
nested objects. Reject boolean-as-integer and numeric string coercion. Trim text,
reject required blanks, and bound lengths before inference. IDs are backend UUIDv4
strings, except local profile id=1. Timestamps are offset-bearing RFC3339 strings,
normalized to UTC; parse timestamps explicitly and reject naive/invalid values.
Past deadlines are allowed. No client supplies XP/status/order/plan_version.

```text
Energy = low | medium | high
Difficulty = easy | medium | hard
QuestlineStatus = active | paused | completed
CheckInContext = {
  goal: string[1..4000], available_minutes: integer[1..1440], energy: Energy,
  deadline: timestamp|null (default null),
  contextual_notes: string[0..2000]|null (default null)
}
ProfileView = {id: 1, total_xp: integer>=0, level: integer>=1}
ProgressView = {completed_count: integer>=0, remaining_count: integer>=0,
                total_count: integer>=1}
QuestView = {
  id: UUID, order: integer>=1, plan_version: integer>=1,
  status: active|paused|completed, title: string[1..100], action: string[1..2000],
  completion_criteria: string[1..1000], estimated_minutes: integer[1..1440],
  difficulty: Difficulty, xp_reward: 10|20|30,
  hint: string[1..1000]|null, starting_action: string[1..1000]|null,
  completed_at: timestamp|null
}
QuestlineView = {
  id: UUID, goal: string, status: QuestlineStatus, available_minutes: integer,
  energy: Energy, deadline: timestamp|null, plan_version: integer>=1,
  revision: integer>=1, progress: ProgressView, current_quest: QuestView|null,
  completed_quests: QuestView[], created_at: timestamp, updated_at: timestamp
}
QuestlineSummary = {
  id: UUID, goal: string, status: QuestlineStatus, deadline: timestamp|null,
  plan_version: integer, revision: integer, progress: ProgressView,
  created_at: timestamp, updated_at: timestamp
}
CheckInView = {
  id: UUID, status: needs_follow_up|ready|consumed, revision: integer>=1,
  context: CheckInContext, question: string[1..300]|null,
  summary: string[1..2000]|null, questline_id: UUID|null
}
```

`current_quest` is active, or the preserved paused quest when the line is paused;
it is null on completed lines. `completed_quests` includes all completed versions,
sorted by completion time/order, with `completed_at` populated. No locked array,
IDs, metadata or contents exist in public DTOs. Progress counts include completed
history plus current-version unfinished work; superseded work is excluded. A
replan may change total_count. Database `position` maps to public `order`.

## Errors, headers and retry safety

Product errors, including sanitized Pydantic validation errors:

```json
{
  "error": {
    "code": "STALE_REVISION",
    "message": "The questline changed. Reload and try again.",
    "retryable": true,
    "request_id": "opaque-request-id",
    "details": {"current_revision": 4}
  }
}
```

`details` is null or safe field names/codes/current_revision; never echo private
input, generated plans, locked IDs, traces or SQL. Codes: 422 `VALIDATION_ERROR`,
`UNSUPPORTED_REQUEST`, `CLARIFICATION_INSUFFICIENT`; 404 `CHECK_IN_NOT_FOUND`, `QUESTLINE_NOT_FOUND` or
`QUEST_NOT_FOUND`; 409 `STALE_REVISION`, `INVALID_STATE`, `QUESTLINE_PAUSED`,
`CHECK_IN_NOT_READY`, `CHECK_IN_ALREADY_USED`, `IDEMPOTENCY_CONFLICT`,
`REQUEST_IN_PROGRESS`; 503 `OLLAMA_UNAVAILABLE`, `MODEL_UNAVAILABLE`,
`STORAGE_UNAVAILABLE`, `STORAGE_BUSY`, `REQUEST_INTERRUPTED`; 504 `AI_TIMEOUT`;
502 `AI_INVALID_OUTPUT` / `AI_UPSTREAM_ERROR`. Unexpected errors use sanitized
500 `INTERNAL_ERROR`. Invalid UUID paths/headers/body fields use 422.

All mutating endpoints except completion require `Idempotency-Key: <UUIDv4>`.
One key identifies one user intent; reuse it after a lost response, create a new
key only for a new/edited intent. Missing/malformed key is 422. The receipt stores
method/path/canonical-body hash; reusing a key for different content/path is 409.
Succeeded retries never rerun AI/mutations: reconstruct the latest safe public
projection of the saved resource. Hint/shrink replay also checks that quest is
still current/active; otherwise return state/visibility error rather than stale
assistance. Failed retryable attempts can be explicitly retried with the same key;
nonretryable errors require correcting the intent/new key.

Pending duplicates return 409 REQUEST_IN_PROGRESS with Retry-After (seconds).
Lease expiry allows interrupted recovery; see [DATABASE_DESIGN](DATABASE_DESIGN.md).
No background jobs, offline queues or automatic transport retries. Revisions are
integers; AI operations recheck captured state at commit. GETs do not change state.
Public responses use Cache-Control: no-store. CORS allows exact local origins,
Content-Type and Idempotency-Key, not credentials/wildcards.
Expose Retry-After to browser clients for REQUEST_IN_PROGRESS recovery.

Common storage/validation/unexpected errors above apply to every endpoint. An
unreachable server cannot return JSON; the frontend must handle network failure.

## Endpoints

### GET /api/health — canonical readiness

No body. Proposed response:

```json
{"status":"ok","components":{"database":{"available":true},"ollama":{"server_available":true,"model_available":true,"model":"qwen3:1.7b"}}}
```

200 status `ok` when all checks succeed; 200 `degraded` if DB works but Ollama/model
does not (state-only operations remain usable); 503 `unavailable` if DB is not
usable. In that 503 case return the same HealthView, not the error envelope.
Read DB/schema readiness and Ollama tags; never generate text or initialize DB in
this request. Ollama required only for its readiness flag; no mutations; idempotent.
Frontend health deadline: 10 seconds; tags request bounded to five seconds.
Current health remains liveness-only until implementation. No `/health` alias is
needed; this explicitly resolves the PRD route difference.

### POST /api/check-in — interpretation / one follow-up

Start body: `{mode:"start", ...CheckInContext}`.
Answer body: `{mode:"answer", check_in_id:UUID, expected_revision:integer>=1,
answer:string[1..2000]}`. These are discriminated models; no other fields allowed.
Response: CheckInView. Start returns 201 when saved, answer returns 200. A succeeded
start retry may return 200 with the existing latest CheckInView, including consumed
state/questline_id. Interpretation requires Ollama. It saves typed user context,
summary, one question/answer and timestamps; no quest/XP mutations.

Follow-up only for essential deliverable ambiguity, never optional deadline/notes.
At most one question across the chain; answer output may only resolve ready or a
recoverable refusal/insufficient answer, never ask a second question. Ready starts
have question=null. Unsupported medical diagnosis/therapy requests return 422,
not a diagnostic answer. Invalid/stale check-in state is 409; unknown check-in 404
`CHECK_IN_NOT_FOUND`; AI/storage errors use shared codes. Format failure saves no
new business context; accepted answer increments check-in revision. Receipts make
retries safe; invalid answers can be edited explicitly without another question.

### POST /api/questlines — generate and save

Body `{check_in_id:UUID, expected_check_in_revision:integer>=1}`.
201 QuestlineView; succeeded retry 200 latest QuestlineView. Check-in must be ready,
unconsumed and same revision. Unknown check-in 404; otherwise conflict 409.
Ollama required. Validate 3–5 meaningful quests before creating line/version/quests
and consuming check-in in one transaction. Backend assigns rewards/trusted fields.
One line per check-in (unique FK); another key for already-consumed context returns
409 CHECK_IN_ALREADY_USED. No plan or XP changes on AI/storage failure. AI errors
use 502/503/504; pending/reused incompatible keys use 409.

### GET /api/questlines — saved summaries

No body. Query `limit=20` (1–100), `offset=0` (>=0), optional
`status=active|paused|completed`. 200 `{items:QuestlineSummary[],limit,offset,has_more}`.
Sort updated_at descending then id for deterministic ties. Empty list is valid.
No current/future quest text in summaries. No Ollama or mutations; idempotent.
Invalid query 422; storage errors use shared codes.

### GET /api/questlines/{id} — selected dashboard and history

No body. 200 QuestlineView; 404 unknown line. No Ollama/mutations; idempotent.
Read a consistent snapshot; explicitly filter current and completed records only.
Never eager-serialize all related quests, plan snapshots, receipts or context logs.

### POST /api/quests/{id}/hint

Body `{expected_revision:integer>=1, question:string[0..500]|null}`;
question defaults null. 200 `{quest_id:UUID,hint:string,questline:QuestlineView}`.
Ollama required; active current quest only. Uses current quest/goal/completed
context, not locked details. Saves validated hint, increments line revision,
succeeds receipt; original action/criteria/reward/status/XP unchanged.
404 unknown/locked/superseded quest; 409 paused/completed/stale; AI errors
502/503/504. Replay checks current state before returning accepted assistance.

### POST /api/quests/{id}/shrink

Body `{expected_revision:integer>=1, reason:string[0..500]|null}`; default null.
200 `{quest_id:UUID,starting_action:string,questline:QuestlineView}`.
Ollama required; same eligibility/errors as hint. Saves a smaller entry action and
increments revision/receipt only. Original action, completion criteria and reward
are immutable; no subquest, automatic completion, XP or unlock.

### POST /api/quests/{id}/complete

Body `{expected_revision:integer>=1}`. No AI, no completion criteria auto-grading.
Explicit user action is the evidence; only current active quest may first complete.
200 `{outcome:"completed"|"already_completed",awarded_xp:0|10|20|30,
profile:ProfileView,questline:QuestlineView}`. First success awards deterministic XP
and unlocks next or finishes line. Same completed quest retry returns
already_completed/0 and current views even with old expected_revision: check ledger
before revision. No Idempotency-Key needed; unique quest completion is authoritative.
404 unknown/locked/superseded; 409 paused/noncurrent/stale on first attempt. All
completion/reward/pointer/profile/ledger writes commit or roll back together.

### POST /api/questlines/{id}/replan

Body `{expected_revision:integer>=1,available_minutes:integer[1..1440],energy:Energy,
deadline?:timestamp|null,contextual_notes?:string[0..2000]|null,
reason?:string[0..1000]|null}`. Omitted optional fields preserve current values;
explicit null clears deadline/notes; goal cannot be changed. Past deadline allowed.
200 QuestlineView. Only active, unfinished lines; 404 unknown, 409 paused/completed/
stale. Ollama required. Read completed milestones and unfinished context locally;
generate/validate 1–5 replacements before changing anything. Commit new version,
superseded unfinished statuses, exactly one new active quest, latest capacity,
revision and receipt together. Completed IDs/content/XP stay unchanged. AI/stale/
storage failure keeps the old line/plan/XP unchanged. Succeeded replay must not
produce another version. Total_count may change; response exposes no locked work.

### POST /api/questlines/{id}/pause

Body `{expected_revision:integer>=1}`. 200 QuestlineView. No Ollama/XP change;
atomically preserve pointer, active quest→paused, line→paused, revision and receipt.
Already paused returns 200 unchanged (record intent receipt); completed line 409,
unknown 404, conflicting first action 409. Receipt replay never reapplies an old
pause after a later resume; it returns the latest projection.

### POST /api/questlines/{id}/resume

Same body/response; no AI. Paused quest→active, line→active, same pointer/version/XP;
revision/receipt commit together. Already active is 200 unchanged; completed 409,
unknown 404/stale first action 409. Replay never undoes a later pause.

### GET /api/profile

No body. 200 ProfileView of singleton profile. No AI/mutations; idempotent.
New initialized profile returns total_xp=0, level=1. Level is computed from persisted
XP; initialization belongs to startup/schema bootstrap, not this GET.

## Existing diagnostics and rollout

Keep existing `GET /api/ai/status` as a local diagnostic returning its current
AIStatus schema (200 availability flags), no DB writes. Retire generic
`POST /api/ai/generate` after the product UI migrates; it is not a P0 product route.
Health readiness/errors/header changes require updating existing hooks/smoke tests
in their authorized phases. The smallest additions beyond the PRD are saved-list,
pause, resume and profile; no quest listing/debug-plan endpoint exposes locked data.
