# Local AI Quest Companion

AppBuildersPH Hackathon 2026 P0: a privacy-first desktop web companion that turns
deliverables and reported time/energy into manageable quests, one current quest
per questline, with deterministic XP and local persistence. The finalized
[PRD v2.0](docs/Local_AI_Quest_Companion_Final_PRD.docx) is the product source of truth.

**Current status: Phase 2 deterministic backend implemented; Phase 1B AI feasibility partial.**
The UI remains the generic landing/status/prompt scaffold. An internal structured
proposal module and developer benchmark exist; semantic quality needs improvement.
SQLite state, completion/XP, saved reads and pause/resume APIs are implemented.
Creation and replacement are internal services accepting validated proposals;
live check-in/generation orchestration and quest UI remain future phases.
Target platform is desktop web, **not PWA**. The PWA
plugin, registration, manifest and cache/update UI have been removed. Previously
used browsers need the scoped cleanup procedure below.

## Stack and structure

| Layer | Technologies and current scope |
| --- | --- |
| `frontend/` | React, TypeScript, Vite, Tailwind CSS and React Router; local bundled assets, no service-worker registration or generated manifest. |
| `backend/` | Python 3.11+, FastAPI, Pydantic Settings, SQLAlchemy, SQLite, HTTPX and Uvicorn; local REST API and Ollama integration. |
| Local AI | Ollama; primary `qwen3:1.7b`, manually selected fallback `qwen2.5:1.5b`; default endpoint `http://127.0.0.1:11434`. |
| `docs/` and `AGENTS.md` | Architecture, conventions, responsibilities, manual verification and AI disclosure. |

Intended flow: React desktop frontend → local FastAPI REST API → Ollama + SQLite,
all on one laptop. Startup initializes a new empty SQLite database and singleton
profile; saved quests/history/XP persist through the backend services. Unknown or
incompatible databases are preserved and reported unavailable, never reset.
The generic frontend's prompts/responses still disappear on reload.
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
no public fixture-creation or AI quest-generation endpoint yet; new databases
have no questlines. See [API contract](docs/API_CONTRACT.md) for the rollout subset.

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
frontend automated test runner or lint command configured.

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
