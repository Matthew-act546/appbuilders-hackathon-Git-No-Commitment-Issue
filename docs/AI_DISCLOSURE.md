# AI use and verification register

This describes Local AI Quest Companion and its pre-existing scaffold. The
[PRD v2.0](Local_AI_Quest_Companion_Final_PRD.docx) selects desktop web, not PWA.
Current code retains generic prompt generation; Phase 1A retired PWA behavior. This is
not a claim that product workflows, model evaluation or license review are complete.
Intended AI operation details are in [AI_DESIGN](AI_DESIGN.md).
See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation boundaries and
[TEAM.md](TEAM.md) for verification ownership.

## Runtime inference

Ollama is the local inference runtime at the default
`http://127.0.0.1:11434`. FastAPI sends the prompt through HTTPX to the configured
installed model and returns generated text. React calls FastAPI, not Ollama
directly. There is no required remote AI API in the application.

| Role | Configured model tag | Selection |
| --- | --- | --- |
| Primary | `qwen3:1.7b` (Qwen3 1.7B) | Default `OLLAMA_MODEL`. |
| Fallback | `qwen2.5:1.5b` (Qwen2.5 1.5B) | Manually set `OLLAMA_MODEL` and restart FastAPI. The model must already be installed. |

Record the actual installed model digest, quantization/runtime metadata and
Ollama version for submission. A tag/name alone is not an immutable artifact
identifier. Fallback is not automatic and no model is downloaded by the API.

The UI still displays general prompt-to-text generation. Phase 3 backend also
supports persistent grounded quest generation/replanning, strict Pydantic,
deterministic quality checks and one local structured review before saving.
[Benchmarks](AI_BENCHMARK.md) show semantic recovery remains PARTIAL: a model can
falsely approve its own plausible-looking plan. Checks do not prove correctness;
unsupported or uncertain plans are rejected and context preserved. No independent
human QA or real user-task success is claimed. Financial arithmetic, date calculations
and validation must be implemented deterministically in Python.

## AI-assisted development

Only Matthew uses Codex CLI for AI-assisted scaffold, architecture and documentation
work. Developers remain responsible for reviewing generated changes, testing
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

Local-only inference depends on retaining a local `OLLAMA_BASE_URL`. The code
accepts configurable HTTP URLs and does not enforce loopback; review demo
configuration before making a local-only claim. Prompts/output currently remain
in browser memory and local service traffic rather than application storage.
Planned Phase 2–4 check-ins/quests/rewards persist in local plaintext SQLite, with
no raw sensitive logs. No product persistence is implemented in Phase 0.
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
| `qwen3:1.7b` weights | TODO: installed digest, source/model card, quantization | TODO: exact model license and any usage/redistribution conditions | NOT VERIFIED |
| `qwen2.5:1.5b` weights | TODO: installed digest, source/model card, quantization | TODO: exact model license and any usage/redistribution conditions | NOT VERIFIED |
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
- Synthetic task-specific evaluation is recorded in [AI_BENCHMARK](AI_BENCHMARK.md);
  real user-task/hardware/offline acceptance is incomplete. Deterministic state/XP
  is implemented; automatic model fallback is not.
- SQLite application records and recovery are implemented/tested with temporary
  Linux files. Browser prompt caching/synchronization is not implemented; the
  generic frontend is not the product quest UI yet.
- Product is desktop web, not an installed PWA. Mobile installation/native AI and
  cross-device service access are excluded; no such capability is claimed.
- Windows demo readiness, operation during actual internet disconnection and
  performance on target hardware require recorded runs of
  [OFFLINE_TESTING.md](OFFLINE_TESTING.md). Mocked tests and viewport emulation are
  not substitutes for those runs.
- FastAPI's optional `/docs` and `/redoc` use default external UI assets; those
  pages may not render fully offline. Core React/API/inference behavior does not
  require them; local `/openapi.json` remains available.
- Licensing, source-license selection and event-specific disclosure/submission
  requirements remain unverified. Confirm them before submission or presentation.
