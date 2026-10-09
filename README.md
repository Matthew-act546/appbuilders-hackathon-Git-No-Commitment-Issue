# AppBuildersPH Hackathon 2026

Two independent local applications: `frontend/` (React, TypeScript, Vite, Tailwind,
React Router and PWA) and `backend/` (FastAPI, SQLAlchemy/SQLite and local Ollama).
No cloud services or runtime CDN assets are required. SQLite has an engine and
session dependency ready for future use; no application tables are created.

Prerequisites: Node.js 20.19+ or 22.12+ (Node 24 LTS recommended), Python 3.11+,
and Ollama installed separately. Dependency installation needs internet access;
the installed applications and already installed models run locally afterward.

## Linux

From the repository root:

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

## Windows (PowerShell)

From the repository root:

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

Open <http://127.0.0.1:5173>. API docs: <http://127.0.0.1:8000/docs>.
Both development servers bind to loopback by default.

## Ollama and configuration

Start Ollama separately with `ollama serve` if it is not already running.
Check installed models with `ollama list`. This scaffold never installs or pulls
models. If needed, explicitly run `ollama pull qwen3:1.7b` yourself.
The backup is `qwen2.5:1.5b`; install it yourself if needed, set
`OLLAMA_MODEL=qwen2.5:1.5b` in `backend/.env`, and restart FastAPI.
There is no automatic model fallback.

`backend/.env` configures `OLLAMA_BASE_URL` (default
`http://127.0.0.1:11434`), `OLLAMA_MODEL`, `DATABASE_URL`, and `CORS_ORIGINS`
(a JSON array of exact origins). Run the backend from `backend/` so the example
SQLite path resolves there. `frontend/.env` sets `VITE_API_BASE_URL`; restart
Vite after changing it and rebuild for production.

`GET /api/health` reports FastAPI health. `GET /api/ai/status` separately reports
Ollama reachability and model installation. `POST /api/ai/generate` accepts
`{"prompt":"Hello"}` and returns `{"model":"qwen3:1.7b","response":"..."}`.
Generation errors use HTTP 503 for connection/missing-model failures, 504 for
timeouts, and 502 for upstream failures. Status checks take at most five seconds;
generation has a two-minute limit. Browser connectivity is only a browser signal
and is not proof that the backend, AI, or internet is available.

## Build and verify offline mode

From `frontend/`:

```bash
npm run typecheck
npm run build
npm run preview
```

Open <http://127.0.0.1:4173>, wait for “App cached and ready to open offline,”
then switch the browser offline and reload. The manifest, local icons, built
assets and service worker are in `frontend/dist/`. Service workers are enabled
in production/preview, not the development server. Updates require the displayed
reload action. API responses and AI prompts are never cached or queued.

The cached frontend works offline; AI inference requires FastAPI and Ollama
on the device hosting the backend. AI does not run inside a mobile browser.
For another device, configure a reachable backend URL and matching CORS origin;
`127.0.0.1` always means that device itself. PWA features require HTTPS except
on localhost/loopback, so plain HTTP LAN access is insufficient for mobile PWA
offline installation.

Backend smoke tests (from `backend/`, using the virtual environment Python):

```bash
python -m unittest discover -s tests -v
```

On Windows use `.\.venv\Scripts\python.exe` in place of `python`.
