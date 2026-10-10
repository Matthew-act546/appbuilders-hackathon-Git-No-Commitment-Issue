# AI use and verification register

This describes Sibol (formerly Local AI Quest Companion) and its pre-existing scaffold. The
[PRD v2.0](Local_AI_Quest_Companion_Final_PRD.docx) selects desktop web, not PWA.
Current code implements the core quest workflow and retains generic prompt generation
as a diagnostic utility; Phase 1A retired PWA behavior. This is
not a claim that product workflows, model evaluation or license review are complete.
Intended AI operation details are in [AI_DESIGN](AI_DESIGN.md).
See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation boundaries and
[TEAM.md](TEAM.md) for verification ownership.

## Runtime inference

Ollama is the local inference runtime at the default
`http://127.0.0.1:11434`. FastAPI sends the prompt through HTTPX to the configured
installed model. Structured quest proposals are validated before persistence;
the diagnostic endpoint returns generated text. React calls FastAPI, not Ollama
directly. There is no required remote AI API in the application.

| Role | Configured model tag | Selection |
| --- | --- | --- |
| Demo primary | `qwen3:4b` (Qwen3 4B) | User-selected Windows configuration; also shown in `backend/.env.example`. |
| Demo fallback | `qwen3:1.7b` (Qwen3 1.7B) | Manually set `OLLAMA_MODEL` and restart FastAPI. The model must already be installed. This remains the Python settings default. |

Record the actual installed model digest, quantization/runtime metadata and
Ollama version for submission. A tag/name alone is not an immutable artifact
identifier. Fallback is not automatic and no model is downloaded by the API.

The UI supports check-in, generation, completion, saved history, pause/resume and
replanning. Current production acceptance uses strict Pydantic schemas and
deterministic essential checks, with one shared bounded correction (at most two
generation calls). It makes no model self-review/approval call. Subjective quality
warnings do not trigger rejection or more inference; schema and essential failures
preserve context/the previous plan for retry. Earlier review-based policies in
[benchmarks](AI_BENCHMARK.md) are historical experiments.

The backend assigns IDs, sequence, status, revisions and XP; AI supplies content
and difficulty only. Python validates dates/capacity and computes rewards/levels.
Completion makes no inference call. Optional completion encouragement is requested
with the plan and grounded in saved quest content. Loading quotes are authored
frontend copy selected by reported energy; they do not make extra AI requests.

The user reported that generated responses passed team QA and that offline startup
and fresh generation worked. These are user reports, not a universal quality or
performance guarantee. Frontend replanning still needs its own live-model/manual
QA. See [demo readiness](DEMO_READINESS.md) for the evidence boundary.

## AI-assisted development

Codex assisted with scaffold/architecture, backend and frontend implementation,
tests, documentation and debugging. Team tool ownership is recorded in
[TEAM](TEAM.md); verify actual operators/session metadata for the submission.
Developers remain responsible for reviewing generated changes, testing
them and verifying claims. Codex is not a runtime dependency or inference service
called by this application.

For submission, record actual development session model/configuration and scope
of assistance, including pre-existing code. A requested model label is not
independent evidence of the model used by a session; verify tool/session details.
Do not claim this development assistant itself works offline or that its service
terms are the same as the licenses of application dependencies.

## Initial downloads and offline operation

| Activity | Initial connectivity/setup | Without internet after setup |
| --- | --- | --- |
| Install Node/Python/Ollama and package dependencies | Obtain installers/packages, npm dependencies and Python wheels from their sources or a prepared local copy. | Installed tools/dependencies can run locally; no internet dependency is added by the scaffold's build/start commands. |
| Install model weights | Explicitly obtain the primary/fallback weights while connected, normally with a deliberate `ollama pull`. No automatic download is implemented. | Installed local models can infer when Ollama and FastAPI remain accessible. Hardware and runtime failures are still possible. |
| Serve desktop frontend | Build local assets, run Vite dev/preview on same laptop; clear only the old app worker/cache if previously installed. | Reload uses running local server, not required service-worker caching. No pending-request offline queue. |
| Generate via desktop UI | Configure/start local FastAPI/Ollama with an installed model. | Services stay accessible over loopback with internet disconnected. Mobile-native inference is out of scope. |
| Use Codex for development | Separate development-tool access/setup and terms; not bundled in the app. | No offline availability claim has been verified. The deployed/local scaffold does not require Codex access. |

The Ollama adapter rejects non-loopback URLs before network access and HTTPX
disables environment proxy use. Keep the configured frontend/backend origins local
too. Saved check-ins, context, quest content, completions and rewards persist in
local plaintext SQLite. Unsaved form text and generic diagnostic prompts/responses
remain in browser memory. Product content is not persisted in browser storage;
detail/check-in URLs identify records to reload from the backend.
Application logging must not include raw sensitive prompts or model output.
Do not equate that with a verified privacy guarantee for browser, OS or runtime
logs. Use synthetic evaluation/demo data.

## Licensing verification required before submission

No license names or redistribution rights are asserted here. Gracianne records
the evidence and Matthew reviews it against the actual build/artifacts. Inspect
the exact upstream model card/license, Ollama runtime license, dependency LICENSE
and NOTICE files, and any applicable development-tool terms. Model-weight terms
can differ from framework/runtime licenses; verify each separately. Check whether
the submission redistributes weights/binaries or only instructions and source.

| Artifact | Version/identity evidence | License/terms evidence and obligations | Status |
| --- | --- | --- | --- |
| Ollama runtime | TODO: installed version and upstream release/source URL | TODO: exact license text, notices and distribution obligations | NOT VERIFIED |
| `qwen3:4b` primary weights | TODO: installed digest, source/model card, quantization | TODO: exact model license and any usage/redistribution conditions | NOT VERIFIED |
| `qwen3:1.7b` fallback weights | TODO: installed digest, source/model card, quantization | TODO: exact model license and any usage/redistribution conditions | NOT VERIFIED |
| React/React DOM, React Router | [package.json](../frontend/package.json) and [package-lock.json](../frontend/package-lock.json); TODO: reviewed exact packages | TODO: LICENSE/NOTICE evidence and attribution obligations | NOT VERIFIED |
| TypeScript, Vite, React Vite plugin, type packages | Same frontend manifests; TODO: reviewed exact packages | TODO: LICENSE/NOTICE evidence and obligations | NOT VERIFIED |
| Tailwind and Vite integration | Same frontend manifests; TODO: reviewed exact packages | TODO: LICENSE/NOTICE evidence and obligations | NOT VERIFIED |
| Legacy vite-plugin-pwa / Workbox | Removed from current dependencies/output in Phase 1A; present in pre-existing scaffold history | TODO: notices if any legacy output is redistributed | NOT VERIFIED |
| FastAPI, Uvicorn, Pydantic/Settings, SQLAlchemy, HTTPX | [requirements.txt](../backend/requirements.txt) and actual installed metadata; TODO: reviewed versions | TODO: per-package LICENSE/NOTICE evidence and obligations | NOT VERIFIED |
| Python/SQLite and transitive/native dependencies | TODO: actual OS/runtime/package inventory | TODO: relevant licenses/notices and distribution obligations | NOT VERIFIED |
| Codex development service/tool | TODO: actual session/tool/version evidence | TODO: applicable service/tool terms and event disclosure requirements | NOT VERIFIED |
| Repository source and local icon assets | TODO: confirm source provenance and team licensing decision; no root LICENSE file is currently present | TODO: chosen source/asset license and required notices | NOT VERIFIED |

For each row, add verifier, date, exact source URL/file, version/digest, actual
license/terms and required actions after review. Do not substitute a remembered
license or guessed model-family license for the exact artifact's evidence. Do
not add downloaded weights, private session logs or secrets to source control.

## Current limitations and unverified claims

- Model-installed status is not proof generation, accuracy or acceptable latency
  will succeed on every machine. Record real results and evaluation cases.
- Synthetic task-specific evaluation is recorded in [AI_BENCHMARK](AI_BENCHMARK.md).
  Later user-reported Windows/AI/offline results and Windows automated regressions
  are separated in [DEMO_READINESS](DEMO_READINESS.md). No paired 4B/1.7B benchmark,
  exact demo-machine latency or physical completion of user tasks is inferred.
- SQLite recovery and the product UI are implemented. Browser tests use fictional
  tasks and temporary storage; no browser prompt caching/synchronization is used.
  Hint/shrink remain unimplemented and advanced Progress remains a foundation.
- Product is desktop web, not an installed PWA. Mobile installation/native AI and
  cross-device service access are excluded; no such capability is claimed.
- The user confirmed restarting all three services while internet was disconnected
  and generating a fresh questline. Detailed hardware/model-digest/timing evidence,
  manual fallback rehearsal and live-model replan QA remain to be recorded using
  [OFFLINE_TESTING.md](OFFLINE_TESTING.md). Mocked tests do not establish those results.
- FastAPI's optional `/docs` and `/redoc` use default external UI assets; those
  pages may not render fully offline. Core React/API/inference behavior does not
  require them; local `/openapi.json` remains available.
- Licensing, source-license selection and event-specific disclosure/submission
  requirements remain unverified. Confirm them before submission or presentation.
