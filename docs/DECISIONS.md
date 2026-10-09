# Phase 0 decisions and conflicts

Authority: complete [PRD v2.0](Local_AI_Quest_Companion_Final_PRD.docx) and the user's
locked decisions. Earlier generic/AralSpace/CampusPilot concepts are superseded.
Phase 0 was documentation only. Authorized implementation records distinguish
current behavior from future product orchestration.

## Locked decisions

| ID | Decision | Consequence |
| --- | --- | --- |
| D01 | Local AI Quest Companion; desktop web app on one laptop, not PWA | PRD §1/§5; retire PWA in Phase 1, retain local serving. |
| D02 | React/TS/Vite/Tailwind + Python 3.11+/FastAPI/Pydantic/SQLAlchemy/SQLite/HTTPX; reuse Router/Settings | Preserve working scaffold; Git/GitHub collaboration; no cloud/auth services. |
| D03 | UI localhost:5173; backend/Ollama 127.0.0.1:8000 / :11434 | Same-host offline operation; keep existing loopback CORS compatibility. |
| D04 | Primary qwen3:1.7b; backup qwen2.5:1.5b; manual switching | User locks tags; actual validity/latency measured before demo. No auto fallback/download. |
| D05 | Canonical GET /api/health, no /health alias required | Preserves clients and /api convention; planned DB/Ollama readiness retains status field. |
| D06 | Implicit local profile id=1, no accounts | XP across saved lines; level derived rather than independently stored. |
| D07 | Easy=10, medium=20, hard=30; level=floor(total_xp/100)+1 | Backend arithmetic only; no penalties/streaks/multipliers. |
| D08 | One current quest per active questline; many saved lines | Detailed rule resolves broad one-at-a-time wording; UI selects one line. |
| D09 | Initial 3–5; replacement unfinished plan 1–5 | Open replan bound allows one remaining action; completed history outside replacement count. |
| D10 | Optional deadline is timezone-aware RFC3339 instant; past dates allowed | Convert to UTC; missed deadline never fails line or deducts XP. |
| D11 | Available minutes 1–1440; energy low/medium/high; bounded text | One session capacity, not total deliverable time; first quest estimate fits available minutes. |
| D12 | At most one follow-up in a check-in chain | Optional fields never trigger questions; answered interaction cannot ask another. |
| D13 | Public DTOs show current/paused quest, completed history/counts only | No locked IDs/title/action/estimate/hint or superseded content. |
| D14 | Pause preserves pointer and changes current quest to paused; resume restores | Complete/hint/shrink/replan require active line; resume before replan; no XP/AI cost for pause. |
| D15 | Unique completion ledger + partial unique current index + transactions/revisions | Backend/DB authority; generate replan outside lock and commit only against unchanged revision. |
| D16 | Small durable idempotency receipts for AI mutations, no background jobs | Safe lost-response/double-submit handling and interrupted-request recovery. |
| D17 | No P1 Quest Journey in P0 demo | PRD §5 priority overrides §13/demo-script suggestion; show plain history/progress. |
| D18 | Deadline October 10, 2026, 10:00 AM Philippine time (UTC+08:00) | Proposed internal freeze 9:00 AM, submission target 9:30 AM; verify official destination/rules. |

## Conflict register

| Current scaffold / PRD conflict | Minimal target action | Phase |
| --- | --- | --- |
| Generic identity/governance | Reconcile docs now; product UI naming later | 0 / 4 |
| PWA manifest/plugin/hooks/cache message | Source/dependency/build removal complete; existing browser profiles need scoped worker/cache cleanup | 1A / demo-browser QA |
| Vite/README UI hostname 127.0.0.1 | localhost configured for dev/preview; previous origins remain allowed by backend CORS | 1A complete |
| /api/health liveness vs PRD /health readiness | Keep /api/health; Phase 1A explicitly preserves liveness; readiness later with DB implementation | 2 |
| Generic generation, no quests | Reuse adapter and diagnostic /api/ai/status; retire raw demo generation after UI migration | 3–4 |
| detail errors and no idempotency header | Typed product errors/validation; permit Idempotency-Key; legacy compatibility until migration | 1–3 |
| No tables/FK enforcement/bootstrap | Designed models and short serialized transactions; no reset of unknown databases | 2 |
| Plain text diagnostic AI, no product generation | Internal strict initial proposal module/benchmark added; semantic quality remains partial; production orchestration later | 1B / 3 |
| PRD model/XP/profile open decisions | User tags, deterministic 10/20/30 XP, 100 XP levels, single local profile | Locked now |
| PRD Journey screen/demo despite P1 priority | Keep Journey excluded; plain completed history for P0 | Locked now |
| Optional FastAPI docs CDN assets | Direct API/JSON schema for offline proof; optional utility only | No required source change |
| No explicit model-weight ignore patterns | Review ignore coverage during Phase 1; weights never belong in repo | 1 |

## Phase 1A implementation record — October 9, 2026

Authorized scope: desktop foundation/PWA retirement only. Removed the PWA plugin,
registration/types/manifest configuration and cache/update messages; retained
Router, API client, local assets and generic AI form. npm updated package and
lockfile together. Vite dev/preview now bind localhost with strict ports.
Backend application source, settings and three diagnostic routes are unchanged;
smoke-test CORS coverage now includes all four supported local origins.

Health stays liveness-oriented as explicitly allowed for Phase 1A. The Phase 0
readiness/error/idempotency contracts remain proposed; no product endpoint, table,
migration or state behavior was implemented. No automatic model switch/download.
Existing installed browser workers require the documented scoped cleanup; there
is no permanent blanket unregister/cache-deletion logic.

Linux type/build, six backend smoke tests, dependency/import checks and real local
browser/API/model checks passed. Manual environment-selected backup inference was
checked in an isolated test backend. These are generic connectivity checks, not
structured-output benchmarks. See [verification record](OFFLINE_TESTING.md#phase-1a-linux-foundation-record-october-9-2026).
Actual internet-disconnection, existing developer-profile cleanup and Windows
demo-machine validation remain pending. Phase 1B can begin when separately authorized;
performance/structured-output evidence must still be collected on actual hardware.

## Phase 1B implementation record — October 9, 2026

Added strict internal proposal/check-in schemas and `OllamaClient.generate_quest_plan`,
reusing the existing HTTPX transport. Use local `/api/generate`, native JSON schema,
non-streaming output, Qwen3 think=false and temperature 0/seed 42 with 4096 context/
1600 output-token cap. Keep the generic API contracts/model environment configuration.
One bounded format/domain retry; connection/timeout/upstream failures stay distinct.
New structured calls enforce loopback and Python deadline arithmetic; no cloud,
automatic fallback/download, DB tables, endpoints, frontend or progression changes.

Repeatable developer CLI: `python -m app.benchmark_ai` from backend/. See
[AI_BENCHMARK](AI_BENCHMARK.md) for 50 scenario runs, three diagnostic calls,
hardware/installed digests, all historical failures and Windows reproduction.
Final two-sweep primary results: 10/10 accepted with no retry, median 8.60 seconds.
Backup solo: 10/10 accepted, one retry, median 8.00 seconds. Earlier partial GPU
placement coincided with five backup timeouts. Unload the previous benchmark model
manually before a controlled switch; do not introduce automatic runtime failover.

**Status PARTIAL:** transport/strict validation/testing criteria met, semantic
product-readiness gate open. Primary substitutes invented assignment work and
Python on ambiguous goals; backup proposes unasked authentication/Heroku and
online tasks. Shape-valid text is not an approved plan. Keep primary configuration
for the next iteration; implement ready-context/one essential clarification in its
authorized phase and re-evaluate those cases. No benchmark quality/Windows/offline
success may be inferred from the 25 passing mocked tests.

Phase 2 deterministic state-engine work is independently ready for authorization;
AI quality and actual demo-hardware/offline evidence still block declaring the P0
AI gate passed. No Phase 2 implementation, commit or push occurred in Phase 1B.

## Chosen assumptions

### Phase 2 implementation decisions

- Six schema-version-one tables implement state: Profile, Questline, PlanVersion,
  Quest, Completion and TransitionReceipt. Check-in context/summary are stored on
  the line and immutable version snapshots; CheckIn/consumption is Phase 3.
  This follows the authorized minimum-entity/simplification instruction.
- Use the contract's paused quest representation; active/paused are mutually
  unique per line. Deferred composite FKs protect same-line pointer/current plan,
  and service postconditions enforce exactly-one and ledger/XP consistency.
- Only pause/resume needs a small durable intent receipt now, so an old pause
  replay after resume cannot undo newer work. No general request leases/job
  infrastructure is implemented. Future AI orchestration still needs D16's
  intent/lease/fencing guarantees before exposing creation/replan/hint/shrink.
- Expose list/detail/profile/complete/pause/resume only; validated creation and
  replacement are internal service primitives. No public seed/test endpoint.
- Health adds DB readiness with 200/503 and keeps status/service compatibility.
  Combined Ollama readiness remains future; existing AI status is unchanged.
- Bootstrap only empty DBs; validate schema/catalog/FKs/state on restart and
  refuse unknown/inconsistent files without resetting them. Future additions
  need an explicit reviewed migration, not create_all on saved databases.
- Phase 1B prompts/settings/results and frontend remain untouched. Semantic AI
  feasibility is still PARTIAL; state correctness does not approve generated text.

Phase 2 Linux verification: `.venv/bin/python -m unittest discover -s tests -v`
from backend/ passed 57/57 (32 new state/API/startup tests + 25 existing tests).
The initial sandboxed HTTP test stalled; its bounded diagnostic run timed out.
Rerunning with sandbox escalation passed, including real file-backed writer
serialization and new-process restart tests. A reference-schema connection
ResourceWarning from the first passing run was fixed; the final run has no such
warning. pip check, compileall, FastAPI/OpenAPI imports, documentation link-target
checks and git diff --check passed. No live model benchmark, disconnected-internet
test, Windows test, frontend edit, Phase 3 work, commit or push occurred.


No job queue, pagination framework, multi-user server, deletes/exports or new
services in P0. List uses bounded limit/offset. Local owner trusts laptop; disclose
plaintext DB. Accepted hint/shrink persist on their quest. All business mutations
increment revision; only replan changes plan_version. Estimates are guidance;
first action fits time, not total plan. No exact generated wording assertions.
Superseded content stays internal/auditable; completed IDs/records are immutable.

## Important unresolved evidence

| Check | Owner | Gate |
| --- | --- | --- |
| Actual demo OS/RAM/CPU/GPU, Ollama version and installed digests | James + Matthew | Phase 1 before performance promises |
| JSON-schema/think=false on actual Windows hardware; semantic plan quality and real offline inference | Matthew + James; Gracianne independent review | Linux format/latency measured in Phase 1B; Windows and product-quality gates remain open |
| Official upload destination/deadline semantics/pitch/Q&A/disclosure rules | Gracianne | Phase 5; PRD's event notes are team-provided, not official verification |
| Exact licenses and repository source-license choice | Gracianne + Matthew | Before submission; disclosure ledger remains NOT VERIFIED |

No unresolved product/state/API design blocker prevents Phase 1. Source PRD is
readable; hardware/runtime evidence is the first implementation gate.
