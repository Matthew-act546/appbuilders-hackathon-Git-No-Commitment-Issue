# P0 implementation roadmap and acceptance gates

Source: complete [PRD v2.0](Local_AI_Quest_Companion_Final_PRD.docx), especially
§5–8/§14–19. The original Phase 0 roadmap is retained below; unchecked tasks are
the original plan, not the current feature inventory. Current Windows/QA status
and the later frontend replan integration are tracked in
[demo readiness](DEMO_READINESS.md). Deadline: October 10, 2026, 10:00 AM Philippine
time (UTC+08:00). Phase 2 backend state implementation now exists; original
checkboxes below are the full roadmap, not the current implementation inventory.
Proposed internal feature freeze 9:00 AM, submission target
9:30 AM; Gracianne verifies official rules/destination. Scope is P0 only.

## Critical path

Read PRD/contracts → demo laptop/local schema-output proof → transactional quest
engine/file persistence → real check-in/generation → current quest/complete/XP UI
→ hint/shrink/replan/pause/resume/saved lines → actual offline/restart/error QA →
disclosure/rehearsal/upload. Never sacrifice transactional rewards, hidden future
content or completed-history preservation for optional polish.

After Phase 0, independent frontend components may proceed against agreed synthetic
DTO fixtures while Matthew builds backend, but no mock loop is a real acceptance
pass. Only one person edits shared frontend API/types/App.tsx at a time. No later
phase begins automatically from this documentation session.

## Phase 0 — documentation and architecture

- [ ] Read all PRD sections/tables; audit current routes/config/code/PWA/Git state.
- [ ] Reconcile requested docs, API/model/state contracts and team ownership.
- [ ] Resolve PRD/scaffold conflicts; capture genuine hardware/submission questions.
- [ ] Verify links/consistency/source hashes; no source/dependency/schema changes.

Owner Matthew, Gracianne consistency review. Gate: implementation-ready docs with
current/proposed distinction and no invented tests/benchmarks. Completion is
reported by the Phase 0 handoff, not by pre-marking subsequent tasks here.

## Phase 1 — foundation and local AI validation

Depends on Phase 0 decisions. Matthew + James:

- [ ] James confirms actual Windows laptop OS/RAM/CPU/GPU, tools, model digests,
  disk space and local ports. Install missing prerequisites only when authorized;
  never pull models automatically.
- [ ] Matthew inventories and retires PWA registration/config/types/dependency
  using [ARCHITECTURE](ARCHITECTURE.md); James clears only app workers/caches on
  each local hostname/port. Verify built output and desktop refresh without worker.
- [ ] Verify intended localhost UI, loopback-only backend/Ollama, CORS explicit
  origins and Idempotency-Key; expose Retry-After to frontend. Preserve legacy
  diagnostics until product migration. Define product error handler/readiness DTO.
- [ ] Spike schema-output format and thinking controls with strict Pydantic. Run
  realistic primary/backup benchmark from [AI_DESIGN](AI_DESIGN.md); measure cold/
  warm latency, memory, validity/retries and offline operation on the actual host.
- [ ] Record model choice/config and proposed budgets; no automatic failover.

Gate: all three services start locally; localhost frontend works after PWA cleanup;
at least realistic 2–6-stage schema outputs are validated on the demo laptop without
remote inference. If neither model meets validity/latency needs, record a blocker,
do not invent performance or loosen trusted-state validation.

## Phase 2 — database and quest state engine

Implementation handoff: six core/state-receipt entities, guarded bootstrap/FKs/
WAL/explicit transactions, public views, saved reads/profile, completion/XP,
pause/resume receipts and atomic validated replacement primitives are implemented.
CheckIn and general AI receipts/leases are deferred to Phase 3/4 orchestration.
The original seven-entity task list below is superseded by this scoped Phase 2
decision; readiness currently checks DB, with AI status remaining separate.

Depends on schema/contract agreement, not cosmetic UI. Matthew:

- [ ] Implement seven SQLAlchemy entities, versioned empty-DB bootstrap/singleton
  profile and explicit SQLite FK/transaction/WAL settings; no destructive resets.
- [ ] Implement current-only public projection, saved summaries and profile level.
- [ ] Implement unique completion ledger + atomic XP/next unlock/final completion,
  revision guards, pause/resume state logic and durable receipt/lease fencing.
- [ ] Test generated-plan insertion using internal test fixtures (not a public
  test endpoint), repeat/concurrent completions, rollback, paused restrictions,
  pointer/version checks, ledger totals and file-backed new-process restoration.
- [ ] Add DB readiness to health; do not claim AI readiness from model installation.

Gate: state API/service tests prove no duplicate XP or double-current quests,
correct levels/final completion and durable progress. No model generates rewards.
James/Lawrence may build agreed components independently; no mock data in final demo.

## Phase 3 — check-in and quest generation

Backend handoff: persistent start/answer/retrieval, grounded local generation,
safe creation/replan, v1 → v2 migration and durable intent fencing are implemented.
The semantic gate is **PARTIAL**: live primary-model plans still lose details,
invent assumptions or repeat completed work; conservative rejection protects
state but reduces successful planning. See AI_BENCHMARK's Phase 3 results.
Frontend integration and reliable semantic usefulness remain open; no Phase 4
screens or hint/shrink APIs were implemented. Do not check the full working-loop
or AI-quality gate merely because backend tests pass.

Depends on Phase 1 AI gate and Phase 2 persistence. Matthew backend; Lawrence
check-in form and James minimal dashboard integration:

- [ ] Strict CheckInContext/one essential follow-up and ready/consumed states.
- [ ] Initial 2–6 proposal generation, domain/schema validation and one bounded
  malformed-output retry; backend assigns IDs/order/status/version/reward.
- [ ] Durable idempotency/unique check-in use; no partial plans on AI/DB failure.
- [ ] Integrate real check-in→current quest→explicit complete→XP→next unlock.
  Render no locked details; sync profile and restore selected line after refresh.
- [ ] Test blank/coerced/extra fields, follow-up limit, duplicate create/lost response,
  refusal of diagnosis/therapy goals and safe recoverable errors.

**First working-loop gate:** actual local model generates a saved line, UI displays
one quest, explicit completion awards mapped XP once and next quest appears; reload
and backend restart preserve that result. This gate precedes adaptive polish.

## Phase 4 — frontend and adaptive features

Depends on first working loop. Matthew state/AI, James dashboard, Lawrence panels:

- [ ] Hint and smaller starting action: contextual, accepted assistance persistent,
  original action/criteria/reward intact, no XP/unlock.
- [ ] Replan unfinished work from updated capacity: validate before transaction,
  preserve completed IDs/XP, supersede old unfinished rows, activate one replacement.
  Protect concurrent completion/replan and stale/expired AI results.
- [ ] Pause/resume, saved line selection/list, completed history, total XP/level and
  updated progress denominator. Complete all three screens, accessibility and
  distinct backend/AI/loading/storage/retry states.
- [ ] Test public payloads/DOM for locked/superseded sentinel leaks across every
  route, assistance behavior, receipt replays after state changes and last quest.

Gate: all required P0 journey/actions integrated with committed backend state;
no optimistic rewards or loss of completed history. No Journey graph/game polish.

## Phase 5 — QA, offline and submission readiness

Gracianne evidence/acceptance/disclosure; James Windows/demo; Matthew fixes;
Lawrence pitch/UX support:

- [ ] Run [OFFLINE_TESTING](OFFLINE_TESTING.md) on actual demo hardware: remove
  internet while retaining loopback; reload and perform local inference; restart
  backend/Ollama/browser with saved state, including after replan/completion.
- [ ] Run deterministic malformed-output/timeout/storage rollback/concurrency tests
  and manual unavailable-service recovery. A mock test does not prove real offline AI.
- [ ] Confirm optional deadline/past dates, follow-up bound, exactly one current,
  no future leak, duplicate XP safety, file persistence and safe failed replan.
- [ ] Record measured model performance, actual tool versions/digests and limitations;
  update disclosures/licenses/pre-existing-code attribution from evidence.
- [ ] Verify official submission rules/page, README/start commands, source availability,
  submission contents and repository hygiene (no private DB/weights/.env).
- [ ] Rehearse the P0 demo and manual fallback; freeze feature work, reserve fix/
  retest/upload time, submit before the team deadline with verified confirmation.

Gate: FR-01–FR-09 all evidenced or explicitly reported failed/blocked (a blocker
does not become a pass). No new features after freeze. Deadline pressure does not
justify false claims, cloud inference or reward/state shortcuts.

## PRD acceptance traceability

| Requirement | Implementation gate | Minimum evidence / owner |
| --- | --- | --- |
| FR-01 check-in | 3 | Typed context, relevant single follow-up/ready, optional deadline / Lawrence + Matthew; Gracianne QA |
| FR-02 local generation | 1 + 3 | Schema-valid useful 2–6 stages from actual local model / Matthew + James |
| FR-03 gating | 2–4 | One current per line; locked sentinel absent in API/DOM / Matthew + James |
| FR-04 hint/shrink | 4 | Contextual assistance; original criteria/status/XP invariant / Lawrence + Matthew |
| FR-05 replan | 4 | Completed snapshots/XP identical; failed/stale result leaves old plan / Matthew; Gracianne QA |
| FR-06 completion/XP | 2–3 | Explicit, atomic, duplicate/concurrent-safe; 10/20/30 and levels / Matthew |
| FR-07 persistence | 2 + 5 | File-backed DB plus refresh/new-process/backend restart restores state / Matthew + Gracianne |
| FR-08 offline | 1 + 5 | Actual disconnected-internet inference with loopback accessible / James + Gracianne |
| FR-09 failures | 3–5 | Model unavailable/schema/timeout/storage errors, no corruption, recovery / Matthew + Lawrence + Gracianne |
| FR-10 Journey | Excluded (P1) | No P0 dependency or demo promise |

## Explicit exclusions and cut order

No P1 Quest Journey visualization; P2 challenges/user rewards; social/friend
challenges, leaderboards, accounts/auth, integrations, avatars, notifications,
PWA, mobile-native packaging, hosted services, streaks/penalties/multipliers/shop,
complex game world, Docker/CI/deployment or mental-health treatment features.
Cut animation/polish first; **all** specified P0 core/adaptive/state/privacy/error
capabilities remain required. If time prevents P0 completion, report missing work
rather than relabel it as implemented or silently redefining the PRD.
