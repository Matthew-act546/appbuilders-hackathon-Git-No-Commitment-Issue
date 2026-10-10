# Desktop offline, restart and failure verification

Sibol P0, PRD §7/§15–18. **This is a reusable manual checklist, not a blanket
completed test report.** The product UI and state/check-in/generation/replan APIs
are implemented; hint/shrink are pending. The user reported successful Windows
startup and an offline restart of all three services followed by fresh generation.
Those reports and developer automation are separated in
[demo readiness](DEMO_READINESS.md). They do not mark every checklist item passed.
Use the [demo guide](DEMO_GUIDE.md) for Windows startup. Use synthetic data and
record actual PASS/FAIL/BLOCKED/NOT RUN with evidence, never expected=actual.

## 1. Demo machine preparation (Phase 1)

- [ ] James records OS/browser versions, CPU/GPU/RAM, node/npm/Python/Ollama
  versions, model tags/digests, Git revision and tester/date. No private environment
  dump. Complete initial downloads while connected; never auto-pull models.
- [ ] Install prerequisites/dependencies using [README](../README.md) only in the
  authorized implementation phase. Confirm `ollama list` includes the configured
  model (primary `qwen3:4b`, manually chosen fallback `qwen3:1.7b`). Missing model is BLOCKED.
- [ ] Matthew/James finish PWA retirement on both localhost and 127.0.0.1 origins,
  dev/preview ports: only this app's registrations/Workbox caches cleared. Verify
  no controller/manifest registration is required. Old cached builds are not proof
  of the desktop product. Source/build retirement is complete in Phase 1A; run the
  cleanup below in each previously used browser. Keep useful local icons; don't
  erase unrelated browser data.
- [ ] Use a dedicated synthetic QA database when testing write/storage failures.
  Never reset/private-copy a real user's database. Record its safe test path, not
  private data. Keep the same DATABASE_URL/working directory on every restart.

### Old service-worker cleanup (Phase 1A)

This is a one-time **browser procedure**, not application startup logic. Removing
the Vite plugin does not unregister an installed worker. Use the same browser
profile that previously opened the app, and repeat for every app origin it used:
`http://localhost:5173`, `http://localhost:4173`,
`http://127.0.0.1:5173`, `http://127.0.0.1:4173`. Origin storage is separate.
Ports/hostnames not previously used need no destructive cleanup. If the current
localhost listener does not answer at 127.0.0.1, temporarily serve the built app
there with `npm run preview -- --host 127.0.0.1` (stop any preview on that port first).
Start only the intended app on the origin being inspected.

1. Rebuild with `npm run build`, start dev or preview using section 2, and open
   that app origin. In Chromium/Edge open DevTools → **Application → Service Workers**.
   Inspect script URL and scope. The legacy scaffold registered `/sw.js` with `/`
   scope; confirm it belongs to this repository's old build before unregistering.
   If another app shares the origin, do not unregister its worker.
2. Unregister only the identified app worker. Under **Application → Cache Storage**,
   inspect cache entries and remove only this app's obsolete Workbox precache
   (normally a `workbox-precache-v2-…` name including the origin; entries contain the
   old AppBuilders HTML/manifest/build assets). Do not delete every origin cache,
   use a blanket Clear site data action, or clear unrelated browser profiles.
   If identity is uncertain, use a fresh dedicated demo browser profile and ask
   the origin's owner to inspect the old one rather than guessing.
3. Close all tabs/windows for this app origin, including any old installed app
   window, then reopen the desktop URL. Hard-reload with DevTools HTTP cache disabled
   for this verification. An optional installed shortcut may be removed separately;
   deleting a shortcut alone is not worker cleanup.
4. Run these **read-only** console checks on the reopened page:

   ```javascript
   navigator.serviceWorker.controller === null
   ;(await navigator.serviceWorker.getRegistrations()).map(registration => ({
     scope: registration.scope,
     script: registration.active?.scriptURL ?? registration.waiting?.scriptURL ?? registration.installing?.scriptURL,
   }))
   await caches.keys()
   document.querySelector('link[rel="manifest"]') === null
   ```

   Expect no controller, no registration for this app, no identified app Workbox
   cache and no manifest link. Unrelated caches/registrations may legitimately
   remain. If a controller remains, close all app tabs and repeat the scoped
   inspection; do not report retirement success for that profile yet.
5. Reload once more and inspect Network: HTML/JS/CSS are fetched from the running
   local server without a service-worker response. No worker/manifest is installed
   again. Record origin, browser/profile, tester/date and evidence. In `frontend/dist/`,
   no `sw.js`, `workbox-*.js` or `*.webmanifest` should exist after a build. Local
   legacy PNG filenames are retained inert assets, not evidence of PWA behavior.

## 2. Start and verify local services (Phase 1)

Run Ollama separately, only if not already served by the OS application/service:

```text
ollama serve
ollama list
```

Linux backend, from repository root in its own terminal:

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Omit reload for the repeatable demo; README development commands retain --reload.
For isolated QA only, set DATABASE_URL to a dedicated file before starting (Linux
example `DATABASE_URL=sqlite:///./qa-demo.db` before the command; PowerShell
`$env:DATABASE_URL='sqlite:///./qa-demo.db'`). Current startup initializes an empty
schema v4 or atomically upgrades a verified supported older schema. Keep important data backed up with
services stopped; never delete an unknown schema to make a test appear successful.

Phase 3 evidence in AI_BENCHMARK was collected while internet remained connected.
After genuinely disconnecting internet while retaining loopback, the product UI
or pipeline CLI can exercise local check-in/generation/SQLite.
Its quality rejections are real failures to obtain a usable plan, not an offline
connectivity failure. Record both separately. The historical Phase 3 runs are not
offline proof; later user-reported offline success is recorded in demo readiness.

Frontend terminal (both platforms), from repository root:

```text
cd frontend
npm run dev
```

For built desktop verification, stop dev, then from frontend/:

```text
npm run typecheck
npm run build
npm run preview
```

Open http://localhost:5173 for dev or http://localhost:4173 for the built demo.
Keep this local frontend server running throughout offline/reload tests. Phase 1A
builds do not generate a PWA manifest or worker; installation/caching is not needed.
Clean old registrations before using a previously installed browser as evidence.

Linux service checks:

```bash
curl --noproxy '*' --max-time 10 http://127.0.0.1:8000/api/health
curl --noproxy '*' --max-time 10 http://127.0.0.1:8000/api/ai/status
curl --noproxy '*' --max-time 10 http://127.0.0.1:11434/api/tags
```

Windows PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health -TimeoutSec 10
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ai/status -TimeoutSec 10
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/tags -TimeoutSec 10
```

- [ ] `GET /api/health` reports `components.database.available` and HTTP 200/503.
  `GET /api/ai/status` separately reports `available`, `server_available` and
  `model_available`. A database health response does not check AI; model
  installation alone does not prove successful inference.
- [ ] Inspect Network panel: application assets/API requests stay on local origins;
  no runtime CDN/cloud inference. Do not use optional CDN-backed /docs or /redoc
  for offline proof; local /openapi.json and direct requests are available.

Optional generic inference smoke check (diagnostic utility, not product QA):

```bash
curl --noproxy '*' --max-time 130 -fsS http://127.0.0.1:8000/api/ai/generate \
  -H 'Content-Type: application/json' -d '{"prompt":"Reply with one short greeting."}'
```

```powershell
$body = @{ prompt = 'Reply with one short greeting.' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/ai/generate -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 130
```

Expect HTTP 200 with configured `model` and nonempty `response`, not exact wording.
The existing prompt form can test the same flow. This is plain-text connectivity
evidence, not structured quest generation or a model-performance benchmark.

## 3. Real check-in, planning and completion (Phases 3–4)

- [ ] Create synthetic goal: “Draft a one-page project brief with objective, audience,
  approach and next step using my local notes.” Time 20 minutes, energy low,
  deadline/notes optional. At most one relevant essential follow-up; missing
  optional deadline must not trigger a question. Answer if essential, then Generate.
- [ ] Capture line ID from /questlines/:id, selected current ID/revision and profile
  XP before completion. Initial total_count is 2–6, one quest visible, criteria/
  estimate/difficulty/reward present. No locked IDs/text in response or DOM.
- [ ] Exercise the API duplicate-completion check below against a current active
  synthetic line, **before completing that quest in UI**. The API call is the
  explicit completion action. Refresh UI and verify exactly one next quest/unlock,
  expected XP and backend-derived level. Do not assert exact model wording.

Linux: from backend/, set ID copied from the synthetic line URL, then run:

```bash
export QUEST_QA_LINE_ID='replace-with-synthetic-questline-uuid'
.venv/bin/python - <<'PY'
import os
import httpx
with httpx.Client(base_url='http://127.0.0.1:8000', trust_env=False, timeout=10) as c:
    line_response = c.get('/api/questlines/' + os.environ['QUEST_QA_LINE_ID'])
    line_response.raise_for_status()
    line = line_response.json()
    assert line['status'] == 'active'
    quest = line['current_quest']
    before = c.get('/api/profile'); before.raise_for_status()
    before_xp = before.json()['total_xp']
    body = {'expected_revision': line['revision']}
    first = c.post('/api/quests/' + quest['id'] + '/complete', json=body)
    first.raise_for_status()
    second = c.post('/api/quests/' + quest['id'] + '/complete', json=body)
    second.raise_for_status()
    a, b = first.json(), second.json()
    assert a['awarded_xp'] == quest['xp_reward']
    assert b['outcome'] == 'already_completed' and b['awarded_xp'] == 0
    assert a['profile']['total_xp'] == b['profile']['total_xp'] == before_xp + quest['xp_reward']
    assert b['profile']['level'] == b['profile']['total_xp'] // 100 + 1
    print('Duplicate completion checked:', b['profile'], b['questline']['progress'])
PY
```

Windows PowerShell (same before-UI-completion condition):

```powershell
$base = 'http://127.0.0.1:8000'
$lineId = 'replace-with-synthetic-questline-uuid'
$line = Invoke-RestMethod -Uri "$base/api/questlines/$lineId"
$before = Invoke-RestMethod -Uri "$base/api/profile"
$questId = $line.current_quest.id
$reward = $line.current_quest.xp_reward
$body = @{ expected_revision = $line.revision } | ConvertTo-Json
$a = Invoke-RestMethod -Uri "$base/api/quests/$questId/complete" -Method Post -ContentType 'application/json' -Body $body
$b = Invoke-RestMethod -Uri "$base/api/quests/$questId/complete" -Method Post -ContentType 'application/json' -Body $body
if ($a.awarded_xp -ne $reward -or $b.awarded_xp -ne 0 -or $b.outcome -ne 'already_completed') { throw 'Duplicate reward check failed' }
if ($a.profile.total_xp -ne ($before.total_xp + $reward) -or $b.profile.total_xp -ne $a.profile.total_xp) { throw 'XP consistency failed' }
if ($b.profile.level -ne ([math]::Floor($b.profile.total_xp / 100) + 1)) { throw 'Level check failed' }
$b.profile
$b.questline.progress
```

These scripts target the implemented product contract and mutate only the selected
synthetic quest. They are instructions, not a record that this manual check ran.
Concurrent completion/rollback tests also belong in backend automated tests; manual
sequential duplicates are not sufficient concurrency evidence.

## 4. Hint, shrink, pause and replan (Phase 4)

Hint/shrink are not implemented: mark their cases BLOCKED, not passed by the
pause/replan results. The remaining controls are available in My Quests.

- [ ] Save current action/criteria/reward/XP/completed-history snapshot. Hint returns
  contextual help. Shrink returns smaller starting_action with original action/
  criteria intact. Neither completes/unlocks/awards XP. Reload retains assistance.
- [ ] Pause: pointer/current content remains, status paused, XP/version unchanged;
  completion/AI actions unavailable. Resume preserves same quest, no penalty. Repeat
  each intent/retry its key without toggling unrelated later state.
- [ ] After at least one completion, use Adjust your pace → Replan remaining stages
  with time 10, energy low and an optional explanation. The frontend preserves the
  saved deadline/notes; optional deadline changes are API-only. Capture before/after
  detail/profile. Completed IDs/content/rewards/
  timestamps and total XP remain identical; version increments once, total count
  may change; one replacement current. Superseded work is not public/current.
- [ ] Retry the same replan key after a lost response: no second plan/version. If
  another tab completes/pauses during generation, stale result must be discarded.
- [ ] Complete final quest: line completed, no pointer/remaining work, no further
  pause/replan/unlock. Repeating that completion awards zero more XP.

## 5. Disconnect internet, retain local communication (Phases 1 and 5)

**Do not enable browser DevTools Offline or block loopback for this test.** Those
modes may block localhost and test a different failure. Disconnect Wi-Fi/Ethernet
internet connectivity while retaining the loopback interface and all three local
servers. All services are on one laptop; no cross-device network is required.

- [ ] Record disconnection method. Confirm an external uncached request fails;
  navigator.onLine alone is not proof. Keep local firewall/loopback communication.
- [ ] Repeat section 2 health/tags and a fresh local model operation. If localhost
  requests fail, record BLOCKED and fix the test setup; do not infer an internet
  inference dependency from blocked loopback.
- [ ] Reload the built desktop app from the running local preview server and saved
  line. Run new check-in/generation and replan using synthetic data; record model
  output validity, latency and request origins. Hint/shrink remain BLOCKED until
  implemented. No automatic downloads.
- [ ] Verify read/completion/XP/pause/resume work too. Show progress from SQLite,
  not a previous cached page or prewritten response. Record actual results per operation.
- [ ] Restore internet after the demonstration/test; leave intended model/settings.

## 6. Restart persistence (Phases 2 and 5)

- [ ] Capture profile XP/level, selected line status/version/revision, current ID,
  accepted assistance and completed records after completion/replan. Use synthetic
  fixtures; store evidence without private notes.
- [ ] Refresh and close/reopen browser on same local server origin. Retrieve saved
  list/profile/detail: snapshots unchanged (ordinary GETs don't increment revision).
- [ ] Stop only FastAPI (Ctrl+C), restart section 2 from same backend directory and
  DATABASE_URL. Reopen selected line/list and compare all saved fields/XP.
- [ ] Stop/restart Ollama; saved reads and rewards remain while AI unavailable;
  generation works again after model runtime readiness. No resetting DB/model pull.
- [ ] Stop/restart all local processes, retaining the database file and dependencies.
  Repeat load/inference with internet disconnected. Successful process restart must
  prove actual application records, not the previous scaffold's scratch/in-memory probe.
- [ ] In controlled automated file-DB tests kill an interrupted request: successful
  ledger/receipts prevent duplicate mutation; uncommitted work rolls back; expired
  pending receipts recover only with fenced attempt/revision. Never use private DB.

## 7. Model, backend and storage failures (Phases 3–5)

- [ ] FastAPI down, frontend running: local UI renders on reload, shows connection
  error, no fake XP/progress; restart/refetch restores committed state.
- [ ] Ollama down (stop only the test instance, or simulate with a confirmed unused
  loopback OLLAMA_BASE_URL port and backend restart): DB remains healthy,
  `/api/health` stays 200, AI status reports unavailable and generation returns 503;
  saved reads/completion/pause/resume still usable. Original
  line/XP unchanged after failed replan. Restore config/runtime and explicitly retry.
- [ ] Missing configured model (confirmed absent tag, no pull): status unavailable,
  recoverable MODEL_UNAVAILABLE, no auto switch. Restore original tag; optionally
  manually choose installed backup, restart and record generation separately.
- [ ] Invalid output/timeout: deterministic mocked tests force malformed JSON,
  extra XP/state fields, coercions, truncated output and timeout. At most two format
  attempts inside total deadline; no partial plan/XP change. Record mocks as mocks,
  not actual model failures observed. Validate recoverable UI separately.
- [ ] SQLite busy/read-only/write failure: inject only into an isolated QA test DB/
  engine (automated fixtures preferred). Test failure between ledger/XP/pointer
  writes and during replan commit: all business writes roll back, error is visible,
  no success/reward UI. Restore storage, refetch and explicitly retry. Do not chmod,
  delete or corrupt a private database to simulate failure.
- [ ] Run schema/ledger/invariant verification after every recovery; review responses
  for locked/superseded data leakage and logs for sensitive input/output.

## Phase 1A Linux foundation record (October 9, 2026)

Executed on the development Linux machine, using Node 26.7.0, npm 12.1.0,
Python 3.14.7, Chromium 152.0.7977.82 and Ollama 0.40.2. This record does not mark
the Windows/product gates below as passed.
No internet-disconnection test or structured-output benchmark was executed.

| Check / command | Actual result |
| --- | --- |
| `npm run typecheck` in frontend/ | PASS |
| `npm run build` in frontend/ | PASS; rebuilt dist has no manifest, sw.js or Workbox bundle/registration |
| `npm ls --depth=0` in frontend/ | PASS; expected React/TS/Vite/Tailwind/Router dependencies, no PWA plugin |
| `.venv/bin/python -m unittest discover -s tests -v` in backend/ | PASS, 6 tests; four-origin CORS, settings override, empty in-memory SQLite/session, mocked model/generation/failure checks |
| `.venv/bin/python -m pip check` in backend/ | PASS, no broken requirements; sandbox pip cache disabled warning only |
| Import/OpenAPI/metadata check (exact command below, in backend/) | PASS: exactly the three existing application API routes and 0 application tables |
| Local endpoint checks and headless Chromium (`node /tmp/quest-phase1a-runtime.mjs`, temporary verification harness) | PASS: existing health/status, four real CORS preflights, dev UI→FastAPI→qwen3 response, manual environment-selected qwen2.5 inference in an isolated backend, and Router fallback/return-home |
| Fresh-profile browser at localhost:5173 and :4173 | PASS: no controller/registrations/Cache Storage/manifest; favicon retained; no core external HTTP requests or uncaught browser exceptions |
| Service failure/recovery | PASS: isolated backend configured to unused local Ollama port reports unavailable/HTTP 503; browser API request blocking gives status/form errors and unblocking/refresh recovers. These are controlled failures, not a stopped real Ollama or disconnected-internet test. |
| Existing developer/browser-profile cleanup, actual Windows machine, real internet disconnection, file-backed product restart persistence | NOT RUN; manual cleanup/hardware QA pending, product persistence requires Phase 2+ |

```bash
.venv/bin/python -c 'from app.main import app; from app.database import Base; expected={"/api/health", "/api/ai/status", "/api/ai/generate"}; actual={p for p in app.openapi()["paths"] if p.startswith("/api/")}; assert actual==expected, actual; assert len(Base.metadata.tables)==0; print("PASS: FastAPI import/OpenAPI; exactly three existing API routes; zero application tables")'
```

The temporary runtime harness and JSON results live under /tmp on this development
machine, not in source control. It reused existing localhost dev/backend/Ollama
services, started isolated test backends/preview/browser for verification, and
did not change .env files or download models. Reproduce the manual service/browser
checks above; do not treat temporary artifacts as a permanent UI test runner.

## 8. Windows demo gate and results

James runs the actual Windows laptop through all gates; Gracianne records evidence,
Matthew fixes state/AI issues, Lawrence supports UX/pitch. Confirm resource/latency
budgets under unplugged internet, restart, manual model switch and a timed P0
rehearsal (verify the event's pitch duration). Journey now presents completed
history; do not describe a full P1 current/locked visualization or PWA/mobile support.

Run existing frontend type/build and backend unittest/pip checks from README;
add product tests when behavior changes. The historical Phase 0 authors did not
execute these checks. Later Windows automation and user reports are recorded in
demo readiness; mocked tests do not prove real offline inference.

| Case | Tester/date, OS/browser/revision/model | Actual evidence/timing/errors | Result |
| --- | --- | --- | --- |
| PWA retired, desktop local assets/origins | — | — | NOT RUN |
| Actual structured local generation | User report, Windows; exact run metadata not supplied | User confirmed working generation and team AI-response QA | PASS (USER-REPORTED) |
| One-follow-up/current-only visibility | — | — | NOT RUN |
| Duplicate/concurrent completion and levels | — | — | NOT RUN |
| Hint/shrink | Current implementation | Operations/controls are unimplemented | BLOCKED |
| Live pause/replan invariants | — | 40 mocked Opera cases cover recovery/invariants; new frontend replan still needs live manual QA | NOT RUN (LIVE REPLAN) |
| Internet disconnected with loopback inference | User report, Windows; exact run metadata not supplied | Restarted Ollama, FastAPI and frontend while disconnected, then generated a fresh questline | PASS (USER-REPORTED) |
| Saved-state equality after refresh/backend/all-process restart | — | Offline startup/fresh generation report does not supply a before/after history/XP snapshot | NOT RUN (DETAILED LIVE RECORD) |
| Model/backend/storage errors and recovery | — | — | NOT RUN |
| Actual Windows performance/rehearsal | — | — | NOT RUN |

This is a partial record with user-reported results; remaining rows need their own
observations. Replace placeholders only after execution, identify mocked vs real
evidence and explain skipped cases. The historical Linux record above remains
unchanged. Record live-model frontend replan QA separately from the earlier UI sign-off.
