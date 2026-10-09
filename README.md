# Local AI Quest Companion

AppBuildersPH Hackathon 2026 P0: a privacy-first desktop web companion that turns
deliverables and reported time/energy into manageable quests, one current quest
per questline, with deterministic XP and local persistence. The finalized
[PRD v2.0](docs/Local_AI_Quest_Companion_Final_PRD.docx) is the product source of truth.

**Current status: working core quest flow with Phase 4C campaign presentation.**
The Phase 4A forest-themed shell is preserved. Home now submits check-ins, presents
the server's clarification, and explicitly generates a saved questline. My Quests
loads saved work as a sequential Campaign Map with 2–3 source-derived checklist
checkpoints, completes current stages with backend-confirmed XP, and supports
pause/resume and refresh recovery. XP/level read the local backend profile; service
status and the existing generic prompt test remain in the header settings dialog.
Campaign progress distinguishes earned campaign XP from lifetime profile XP. Checklist
marks are temporary; only whole-stage completion is saved. Initial plans remain
2–6 stages selected by the local model for the whole goal, without padding.
Session time guides the first action, not total campaign duration. Replanning
caps completed plus remaining stages at six and preserves all earned progress.
This is an approved post-PRD enhancement; PRD v2.0 remains unchanged. SQLite v3
startup preserves existing campaigns while updating the plan-count constraints;
stop the old backend and back up important SQLite data before restarting.
Journey and advanced Progress/history screens remain foundations. An internal structured
proposal module and developer benchmark exist; semantic quality needs improvement.
SQLite state, completion/XP, saved reads and pause/resume APIs are implemented.
Persistent check-ins, local generation and replanning APIs now join the existing
state engine. Schema and essential-constraint failures are rejected with saved
context available for retry; subjective quality findings are now warnings rather
than mandatory approval gates. Real-model usefulness still varies. Phase 4B's single live primary-model
integration attempt was semantically rejected, not saved. Adaptive UI and optional
Journey/progress integration remain Phase 4C work.
Target platform is desktop web, **not PWA**. The PWA
plugin, registration, manifest and cache/update UI have been removed. Previously
used browsers need the scoped cleanup procedure below.

## Stack and structure

| Layer | Technologies and current scope |
| --- | --- |
| `frontend/` | React, TypeScript, Vite, Tailwind CSS and React Router; local bundled assets, no service-worker registration or generated manifest. |
| `backend/` | Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy, SQLite, HTTPX and Uvicorn; local REST API and Ollama integration. |
| Local AI | Ollama; primary `qwen3:4b`, manually selected fallback `qwen3:1.7b`; default endpoint `http://127.0.0.1:11434`. |
| `docs/` and `AGENTS.md` | Architecture, conventions, responsibilities, manual verification and AI disclosure. |

Intended flow: React desktop frontend → local FastAPI REST API → Ollama + SQLite,
all on one laptop. Startup initializes a new empty SQLite database and singleton
profile; saved quests/history/XP persist through the backend services. Unknown or
incompatible databases are preserved and reported unavailable, never reset.
Diagnostic prompts/responses and unsaved form text still disappear on reload.
Saved check-ins restore through the opaque `?check_in=<id>` URL; questline detail
routes reload backend state. No goals, notes or quest plans are stored in browser storage.
No cloud database, remote AI API or runtime CDN asset is required by the frontend
or core API/inference flow. FastAPI's optional interactive API documentation uses
its default external assets; see the offline limitations below.

## Requirements

- Node.js matching `^20.19.0 || >=22.12.0` in `frontend/package.json`, and npm.
- Python 3.11+ with virtual-environment support; Windows commands use the `py`
  launcher and the virtual-environment executable directly.
- Ollama installed separately and sufficient local resources for the chosen model.
- A modern desktop browser. Dependencies, installers and model
  weights need initial downloads or prepared local copies; runtime services stay
  local afterward. Exact frontend versions are in `package-lock.json`; backend
  direct dependencies are pinned in `requirements.txt`.

## Linux setup and start

From the repository root, in the frontend terminal (copy the example only on first
setup; preserve existing `.env` configuration):

```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

In another terminal, from the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Windows setup and start (PowerShell)

From the repository root (preserve any existing `.env` instead of overwriting it):

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

In another terminal, from the repository root (use an installed Python 3.11+):

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Start Ollama and select the model

Start Ollama separately with `ollama serve` if it is not already running.
In its own terminal, on Linux or Windows:

```text
ollama serve
```

In another terminal:

```text
ollama list
```

This scaffold never installs or pulls models. If the primary is absent, deliberately
run `ollama pull qwen3:1.7b` while connected. The fallback is `qwen2.5:1.5b`;
install it yourself if needed (`ollama pull qwen2.5:1.5b`), set
`OLLAMA_MODEL=qwen2.5:1.5b` in `backend/.env`, and restart FastAPI. There is no
automatic fallback. Do not run `ollama serve` twice if the OS application/service
is already serving the endpoint.

## Configuration

| Variable | File | Default |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `frontend/.env` | `http://127.0.0.1:8000` (no `/api` suffix) |
| `OLLAMA_BASE_URL` | `backend/.env` | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | `backend/.env` | `qwen3:1.7b` |
| `DATABASE_URL` | `backend/.env` | `sqlite:///./app.db` |
| `CORS_ORIGINS` | `backend/.env` | JSON array of `http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:4173`, `http://localhost:4173` |

See [frontend/.env.example](frontend/.env.example) and
[backend/.env.example](backend/.env.example). Pydantic Settings loads backend
configuration; process environment values override `.env`. Restart FastAPI after
changes. Run it from `backend/` so the relative SQLite path stays consistent.
Restart Vite after frontend changes and rebuild production assets. `VITE_*`
variables are public browser configuration, not a place for secrets. Do not commit
`.env`, databases, model weights, dependencies, virtual environments or private data.

## URLs and API

| Service | Local URL |
| --- | --- |
| React development | <http://localhost:5173> |
| Built frontend preview | <http://localhost:4173> |
| FastAPI | <http://127.0.0.1:8000> |
| Interactive API docs | <http://127.0.0.1:8000/docs> |
| JSON API schema | <http://127.0.0.1:8000/openapi.json> |
| Ollama | <http://127.0.0.1:11434> |

Vite dev/preview and the documented Uvicorn commands bind to loopback. Vite ports
are strict. The frontend and backend run separately; starting one does not start
the other or Ollama.
Vite dev and preview bind `localhost` by default. The backend still permits the
previous 127.0.0.1 frontend CORS origins for compatibility; use localhost for the
documented frontend commands.

`GET /api/health` reports database availability (200 `ok`, 503 `unavailable`),
preserving the existing `service` field; it does not check Ollama.
`GET /api/ai/status` separately reports Ollama reachability and model installation
with availability flags, including when unavailable. `POST /api/ai/generate` accepts
`{"prompt":"Hello"}` and returns `{"model":"qwen3:1.7b","response":"..."}`.
Generation errors use HTTP 503 for connection/missing-model failures, 504 for
timeouts, and 502 for upstream failures. Status checks take at most five seconds;
generation has a two-minute limit. Browser connectivity is only a browser signal
and is not proof that the backend, AI, or internet is available.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full current route semantics.

State-only endpoints: `GET /api/profile`, `GET /api/questlines`,
`GET /api/questlines/{id}`, `POST /api/quests/{id}/complete`, and
`POST /api/questlines/{id}/pause` / `resume`. Writes accept
`{"expected_revision":1}`; pause/resume also require a UUIDv4 `Idempotency-Key`.
Detail responses reveal only the current quest and completed history. There is
no public fixture-creation endpoint; new databases have no questlines.
Phase 3 adds `POST /api/check-in` (`mode:start` or `mode:answer`),
`GET /api/check-in/{id}`, `POST /api/questlines` and
`POST /api/questlines/{id}/replan`. These mutations require Idempotency-Key.
See [API contract](docs/API_CONTRACT.md) for executable JSON shapes and recovery.

Startup performs the explicit, atomic v1 → v2 migration only on a verified v1
schema. Existing state/XP is preserved. Before upgrading a database containing
important data, stop services and keep a backup; never delete a rejected database.

## Build and backend checks

From `frontend/`:

```bash
npm run typecheck
npm run build
npm run preview
```

The build also runs type checking. `preview` stays running until Ctrl+C. Backend
tests use standard-library unittest, mocked Ollama and temporary SQLite files.
State tests include concurrent completion, rollback and new-process persistence;
they do not prove real offline inference or Windows demo readiness.

From `backend/` on Linux (the earlier setup activates the virtual environment;
the explicit path also works without activation):

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
```

From `backend/` on Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

With a virtual environment activated, the existing
`python -m unittest discover -s tests -v` command remains valid. There is no
frontend lint command configured. Phase 4B adds dependency-free development tests:

```bash
# From frontend/; verified on Linux with Node 26.7.0
node --test --test-isolation=none tests/validation.test.mjs tests/campaign.test.mjs
node tests/core-flow.mjs
```

The boundary tests use Node's native TypeScript support. Browser tests require
Chromium (`CHROMIUM_BINARY` may specify its executable), the existing backend
virtual environment, and a production build. They start isolated test services on
8004/4184/9229, use temporary SQLite and fictional mocked Ollama, and write evidence
to a printed temporary directory. They never seed the user's database. No test
dependency or package script was added; these commands were not verified on Windows
or other Node versions. `node tests/core-flow.mjs --live-campaign` adds one real
short-campaign generation and full frontend completion test using temporary SQLite.
`node tests/core-flow.mjs --live-ai` explicitly adds one real
primary-model check-in/generation attempt; a recoverable rejection is reported
separately from passing mocked scenarios and does not establish model quality.

Phase 4B Linux results: frontend typecheck/build and diff checks passed, boundary
tests passed 5/5, browser scenarios passed 14/14, and backend regressions passed
90/90. One live `qwen3:1.7b` attempt returned semantic rejection with context retained
and no questline saved. Windows and actual internet-disconnection tests remain pending.

Development-only production-pipeline benchmark (fictional inputs and temporary
SQLite storage), from `backend/`:

```bash
.venv/bin/python -m app.benchmark_pipeline --model qwen3:1.7b --output ../docs/benchmarks/new-phase3-run.json
```

On Windows use `.\.venv\Scripts\python.exe -m app.benchmark_pipeline` with the
same arguments. Existing output files are refused. A completed benchmark does
not imply semantic success; see the Phase 3 section in [AI benchmark](docs/AI_BENCHMARK.md).

## Desktop offline operation and old PWA cleanup

The desktop scaffold serves local built assets from a running local frontend
server; FastAPI, SQLite and installed Ollama/model run on the same laptop. Disconnect
internet while retaining loopback. Service-worker caching/installation is not a
product requirement. A stopped frontend server may prevent reload. Production
builds contain ordinary HTML/JS/CSS and local icons; no manifest, Workbox bundle or
service worker is generated. API responses and pending requests are not cached or
queued. Unused legacy PNG icons remain inert assets; the ordinary favicon is retained.

A browser that previously opened the PWA can still serve an old cached build.
For each previously used app origin (localhost or 127.0.0.1, port 5173 or 4173),
use DevTools **Application → Service Workers** to identify and unregister only
this app's old `sw.js`, then remove only its identified Workbox cache under
**Cache Storage**. Close the app's tabs and reopen/hard-reload the new build.
Confirm `navigator.serviceWorker.controller === null` and that this app's
registration/cache are absent. Do not clear unrelated workers or browser data.
The full origin-scoped procedure and verification commands are in
[Offline testing: old service-worker cleanup](docs/OFFLINE_TESTING.md#old-service-worker-cleanup-phase-1a).
No permanent blanket cleanup logic has been added to the application.

To test offline AI, disconnect internet while keeping loopback communication and
all local servers available. Browser DevTools Offline can block localhost and is
not the correct test. Actual internet-disconnection and Windows demo testing
remain unexecuted in Phase 1A; follow [docs/OFFLINE_TESTING.md](docs/OFFLINE_TESTING.md)
and record actual results. Local AI Quest Companion uses one laptop with local
servers. Cross-device serving, PWA/mobile packaging and HTTPS deployment are
outside this P0 scope.

FastAPI's default `/docs` and `/redoc` pages reference external UI assets and may
not render fully without internet. They are optional; use local API requests or
`/openapi.json` for offline verification. The React UI and core API/inference flow
do not require those pages or their assets.

## Governance and documentation

- [AGENTS.md](AGENTS.md) — coding-agent rules, instruction hierarchy and done criteria.
- [Architecture](docs/ARCHITECTURE.md) — components, API, configuration and limits.
- [Conventions](docs/CONVENTIONS.md) — code, branches, review and testing practices.
- [Team](docs/TEAM.md) — ownership and independent documentation/QA deliverables.
- [Offline testing](docs/OFFLINE_TESTING.md) — executable Linux/Windows manual checklist.
- [AI disclosure](docs/AI_DISCLOSURE.md) — AI use, downloads and license verification placeholders.
- [P0 roadmap](docs/P0_IMPLEMENTATION_PLAN.md) — ordered phases, owners and acceptance gates.
- [API contract](docs/API_CONTRACT.md) — proposed typed P0 endpoints and hidden-data boundaries.
- [Database design](docs/DATABASE_DESIGN.md) — schema, constraints and transactions.
- [Quest rules](docs/QUEST_RULES.md) — lifecycle, deterministic XP and replan safety.
- [AI design](docs/AI_DESIGN.md) — operation schemas, validation and benchmark plan.
- [AI benchmark](docs/AI_BENCHMARK.md) — Phase 1B measurements, quality failures and Windows reproduction.
- [Frontend plan](docs/FRONTEND_PLAN.md) — desktop screens/components and integration.
- [Decisions](docs/DECISIONS.md) — locked choices, conflicts and unresolved evidence.

Check results and licenses must be recorded from actual evidence. The manual
checklist is a blank QA record, not a declaration of demo-machine readiness.

Phase 3B hotfix: physical-task criteria and one shared quality correction are now
supported; generic cooking asks which dish/available ingredients to use. Errors
distinguish rejected model output from uncertain review and retain the check-in.
The final targeted cooking/snack/desk run saved 3/3, but content remained only
partially useful; the full 12-case comparison saved 3/12. Semantic reliability
remains PARTIAL. See [measured hotfix evidence](docs/AI_BENCHMARK.md#13-phase-3b-everyday-goal-hotfix).

Resumed hotfix verification: a real Qwen3 no-cook snack questline was saved, all
three quests completed through the frontend, and completion/40 XP retained after
refresh in isolated test storage. Missing presentation topics now clarify; requested
slide/practice coverage is checked. The specific AI-introduction scenario still
fails quality checks, so semantic reliability remains PARTIAL.

Phase 4C campaign presentation verified: frontend typecheck/build, 11 frontend
tests, 111 backend regressions, 16 mocked browser scenarios and one real local
Qwen3 campaign walkthrough passed. The short snack goal generated three stages;
explicit UI completion confirmed 40 campaign XP and survived refresh.
`node tests/core-flow.mjs --live-campaign` reproduces the isolated browser check.
At that Phase 4C checkpoint six-stage generation was deferred; checklist marks are temporary, while whole-stage
completion and XP persist in SQLite. Existing AI quality limitations are unchanged.

Phase 3C reliability recovery is **PARTIAL**. Scoped semantic repair and native
schema compatibility fixes passed 134 backend regressions. The paired final local
Qwen3 run saved 4/6 actionable scenarios; Codex content inspection rated only 2/6
saved plans fully acceptable. An additional live presentation was saved and
completed through the frontend, with backend-confirmed XP retained after refresh,
but still had weak criteria. This verifies integration, not reliable content.
Cooking repair and invented endpoint behavior remain failures. See
[Phase 3C measurements and reproduction](docs/AI_BENCHMARK.md#14-phase-3c-bounded-semantic-recovery).

Phase 3D removes model self-review from production acceptance. Structured schema
and essential constraints remain enforced, with at most one correction. The same
six actionable Qwen3 cases saved **5/6**, versus 4/6 in Phase 3C; median full-workflow
latency was **12.41 s**. Codex inspection rated four saved candidates usable and
one partial; independent human QA is pending. The three-test goal still fails
because the model proposes two tests and invented HTTP behavior. Checks passed:
141 backend tests, 11 frontend tests, typecheck/build, 16 mocked browser regressions
and a separate real presentation save/completion/refresh. General reliability
remains **PARTIAL**. See [Phase 3D evidence](docs/AI_BENCHMARK.md#15-phase-3d-essential-only-acceptance).

Adaptive sizing verification: 154 backend tests, 12 frontend tests and 18 browser
scenarios passed, including two/six-stage unlocking, one-time XP, privacy and refresh.
The final two-case Qwen3 run saved a four-stage sandwich and a five-stage study
guide (35 estimated minutes with 20 available). Count support is implemented;
model sizing/usefulness remains PARTIAL: the sandwich is over-fragmented and the
study guide omits a requested third example. See
[adaptive sizing evidence](docs/AI_BENCHMARK.md#16-adaptive-campaign-sizing-26-stages).

Quest completion now shows a forest-themed “Quest Complete!” panel with a
quest-specific message, backend-confirmed XP and unlocked stage number. Continue
Journey returns focus to the Campaign Map. Messages also remain in completed
history after refresh. Optional copy is requested in the existing plan-generation
call; unsupported or missing copy falls back to the completed title/action.
Completion makes no Ollama request. Current/locked-stage messages stay private.

Schema v4 adds one nullable quest column through an atomic v3→v4 migration;
existing campaigns, history and XP are retained. Back up important SQLite data
before updating the backend. See [database migration details](docs/DATABASE_DESIGN.md).
Enhancement verification on Linux: 163 backend tests, 14 frontend tests,
typecheck/build and 20 mocked-Ollama Chromium cases passed. One real qwen3:1.7b
two-stage campaign generated in 7.52 seconds, completed through the frontend with
a simulated Ollama outage, awarded 30 XP and restored both messages after refresh in an
isolated database. UI completion was synthetic; no physical snack-making,
Windows-machine or disconnected-internet test is claimed. Reproduce with
`node tests/core-flow.mjs --live-campaign` from `frontend/` after building.
