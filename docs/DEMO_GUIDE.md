# Sibol Windows demo guide

Use this guide after the working Windows installation is complete. It starts
existing local services and rehearses implemented features. No installation,
model download or submission is performed by this document. Check
[demo readiness](DEMO_READINESS.md) and [AI disclosure](AI_DISCLOSURE.md) before
presenting results; official event rules and timing still need team verification.

## Start the three local services

Open PowerShell terminals at the repository root. Keep them running during the
demo. Use only one process on each listed port.

1. Ollama: if the desktop app/service already serves port 11434, use it. Otherwise
   run `ollama serve` in its own terminal. Run `ollama list` in a separate terminal
   to confirm the primary `qwen3:4b` is installed. Prepare `qwen3:1.7b` in advance
   for manual fallback; neither model is downloaded automatically.
2. FastAPI: stop any previous backend using port 8000, then start from `backend/`.
   For a rehearsal with fictional data, the following selects a dedicated SQLite
   file; keep the same file and working directory across restarts.

   ```powershell
   cd backend
   $env:DATABASE_URL = 'sqlite:///./qa-demo.db'
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   This process uses `qa-demo.db` instead of the ordinary app database. Do not copy
   private records into it. After stopping the rehearsal backend, remove this
   terminal override with `Remove-Item Env:DATABASE_URL` before normal startup.
3. Frontend: build and serve the local assets in another terminal.

   ```powershell
   cd frontend
   npm run build
   npm run preview
   ```

Open **http://localhost:4173**. Development mode (`npm run dev`) instead uses
http://localhost:5173. If this browser used the old PWA, follow the
[scoped cleanup procedure](OFFLINE_TESTING.md#old-service-worker-cleanup-phase-1a).

Check services from a spare PowerShell terminal:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health -TimeoutSec 10
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ai/status -TimeoutSec 10
```

Health reports database readiness; AI status independently reports Ollama and the
selected installed model. A healthy database alone does not prove inference works.
The chosen primary is `qwen3:4b`; the Python settings default remains `qwen3:1.7b`,
so verify the returned model rather than assuming the active configuration.

## Rehearse the implemented flow

Use a fictional goal such as “Draft a one-page project brief with objective,
audience, approach and next step using my local notes.” Choose 20 minutes and low
energy. Supply relevant fictional notes if needed. Allow real generation time;
no latency or exact stage count is promised.

1. **Home:** submit the check-in, answer an essential clarification if shown, then
   explicitly generate. Show the centered loading card and energy-aware quotes.
2. **My Quests:** inspect the saved capacity, campaign progress and one current
   stage. Locked stages remain anonymous. Checklist marks are temporary; they do
   not award XP or count as saved completion.
3. **Complete one stage:** for this synthetic walkthrough, explicitly complete it
   to demonstrate the state transition. The popup shows backend-confirmed XP;
   dismiss it and verify the viewport and controls recover. This demonstrates
   software behavior, not physical completion of the fictional task.
4. **Adjust your pace:** pause and resume, confirming the same current stage and
   unchanged XP. Replan remaining stages with 10 minutes, low energy and an optional
   explanation. Inspect the returned content before describing it as useful.
5. **Verify replan preservation:** compare completed stage IDs/details/times and
   earned XP before/after. Only unfinished work changes. The goal, saved deadline
   and original notes remain; the total stage count may change. Refresh to verify
   persistence. This is the pending live-model QA check for the new frontend flow.
6. **Journey:** select the saved questline and open completed-stage details. Show
   actual completion dates and questline XP. History is read-only.

Completion rewards are easy=10, medium=20 and hard=30; level is
`total_xp // 100 + 1`. Replanning and pause/resume do not award or deduct XP.
Hint/shrink are unimplemented; advanced Progress is a foundation. Keep those
limitations explicit in the pitch. The [synthetic UI screenshots](screenshots/sibol-ui/README.md)
illustrate the mocked regression run, not live-model output or offline proof.

## Offline and recovery rehearsal

Disconnect internet while keeping loopback available. Keep all three services
running, reload the app and generate a fresh fictional questline. Then restart
Ollama, FastAPI and the frontend with the same database and repeat generation.
Record what actually happened in [offline testing](OFFLINE_TESTING.md); the user
already reported this sequence working, but exact timings and hardware metadata
were not supplied. Browser DevTools Offline can block localhost and is unsuitable
for this check.

For manual fallback, stop FastAPI and change only `OLLAMA_MODEL` in the existing
`backend/.env` to `qwen3:1.7b`, then restart FastAPI from the same directory with
the same database. Confirm AI status and generate a fresh fictional plan. Restore
`qwen3:4b` and restart afterward if that is the intended demo configuration.
The source example also shows the primary/fallback settings. Preserve unrelated
environment values and never publish the actual `.env`.

If inference fails, show the recoverable error and explicitly retry. An uncertain
response may already have committed: use the existing same-action retry to recover
rather than starting a competing request. If another tab changed the questline,
reload canonical state before making a new decision. Failed replanning keeps the
previous plan and completed XP. If database health returns 503, preserve the file,
close external SQLite editors and investigate startup/schema/storage errors;
deleting the database is not a repair procedure.

## Evidence to collect before submission

Record tester/date, Git revision, Windows/browser and CPU/GPU/RAM, runtime versions,
installed model digests/quantization, actual generation/replan timings and observed
errors. Complete live replan QA and manual fallback rehearsal. Verify exact
licenses/source provenance and official upload, deadline, disclosure and pitch
rules. None is certified by this guide. Keep evidence synthetic and consult the
[readiness checklist](DEMO_READINESS.md) for outstanding items.
