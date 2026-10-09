# Development conventions

Read [../AGENTS.md](../AGENTS.md), [../README.md](../README.md) and
[ARCHITECTURE.md](ARCHITECTURE.md) before editing. Code conventions below follow
the scaffold; branch/review practices are team rules introduced in this phase.
Product scope is Local AI Quest Companion P0, governed by the
[final PRD v2.0](Local_AI_Quest_Companion_Final_PRD.docx) and
[DECISIONS.md](DECISIONS.md). Phase 0 changes docs only. The desktop target is not
a PWA; current service-worker code is retired only in authorized Phase 1 work.

## TypeScript and React

- Use TypeScript with the existing strict configs. Keep explicit props and API
  request/response types; use `import type` for type-only imports. Prefer `unknown`
  over `any` for untrusted values and validate at boundaries when needed.
- Match the existing two-space indentation, single quotes and no-semicolon style.
  No formatter or linter is installed; do not claim a lint check passed.
- Use PascalCase component/page files (`StatusCard.tsx`, `Home.tsx`), `use`-prefixed
  camelCase hooks (`useServiceStatus.ts`), and camelCase helpers (`api.ts`).
- Keep route pages in `src/pages/`, reusable UI in `src/components/`, lifecycle
  behavior in `src/hooks/`, HTTP helpers/types in `src/lib/`, and routes in `App.tsx`.
  Reuse those locations before adding new layers.
- Use Tailwind utilities and the existing `@tailwindcss/vite` integration plus
  `@import "tailwindcss"`; do not introduce a CDN or obsolete parallel setup.
- Provide visible loading and error states, accessible form labels and disabled
  duplicate-submit controls. Cancel abandoned requests and handle timeouts.
- Render AI output as untrusted text. Do not inject raw HTML or execute model
  output. Avoid persisting prompts or private data in browser storage without an
  explicit requirement and defined handling policy.

## Python and persistence

- Target Python 3.11+. Use four-space indentation, snake_case modules/functions,
  PascalCase classes, type hints and the current double-quote style.
- Keep settings in `app/config.py`, engine/session support in `app/database.py`,
  API schemas in `app/schemas.py`, endpoints in `app/routes.py`, and Ollama HTTP
  behavior in `app/ollama.py`. Keep `app/main.py` focused on application setup.
- Use async HTTPX for Ollama I/O and reuse the lifespan-managed client. Keep
  timeouts and upstream failure handling; do not call remote AI services.
- Use Pydantic for request/response validation. For future structured AI results,
  validate both shape and deterministic business constraints before saving.
- Follow [DATABASE_DESIGN](DATABASE_DESIGN.md) and [QUEST_RULES](QUEST_RULES.md)
  for new models/state services: backend IDs/rewards, unique completions, short
  serialized writes, revision/receipt guards and no DB write lock during inference.
- Use SQLAlchemy for SQLite work. Close sessions through `get_session`; commit
  successful writes explicitly and roll back failed transactions. The current
  scaffold has no application tables or write endpoints.
- Perform financial arithmetic, date calculations and validation deterministically
  in Python. For money, select an explicit decimal/rounding policy; never accept
  LLM arithmetic or generated SQL as authoritative.
- Use synthetic fixtures and isolated temporary/in-memory databases in tests.

## REST API and errors

- Keep application endpoints under the existing `/api` router prefix. Use GET for
  reads and POST for generation or future creation. Add only agreed endpoints;
  align schemas and frontend types whenever the contract changes.
- Keep snake_case JSON keys. Current raw generation uses `{prompt}` and
  `{model,response}`; it is scaffold-only. Proposed product DTOs/errors/headers
  follow [API_CONTRACT](API_CONTRACT.md); never serialize complete ORM plans.
- Use appropriate status codes and clear client-facing errors without secrets or
  private prompts. Existing upstream errors use 503/504/502 with string `detail`;
  validation uses 422 with structured details.
- An AI status response with HTTP 200 and `available: false` is an availability
  report, not successful inference. Current `/api/health` is liveness-only;
  planned readiness keeps that canonical route and distinguishes DB from AI.
- Quest rewards are deterministic 10/20/30, level=total_xp // 100 + 1. Completed
  history/XP must survive replan; hide future/superseded content from every DTO.
  Only explicit completion awards XP; hint/shrink are assistance, not completion.
- Preserve distinct browser/backend/AI indicators. Do not gate local requests
  solely on `navigator.onLine`; local services can work without internet.

## Configuration and generated files

Use the five existing configuration names: `VITE_API_BASE_URL`, `OLLAMA_BASE_URL`,
`OLLAMA_MODEL`, `DATABASE_URL` and `CORS_ORIGINS`. Use JSON arrays for CORS origins.
Document new variables in the relevant `.env.example` and architecture/README.
Restart the relevant process after edits; production frontend changes need a
rebuild. A fallback model change is manual and also needs a backend restart.

Do not commit secrets, credentials, API keys, private user data, `.env` files,
databases, model weights, `node_modules`, virtual environments, `dist/` or cache
files. `.env.example` must contain safe example values only. Review staged changes
and `git status --short`; ignore patterns are not a substitute for that review.

## Branches and pull requests

The current integration branch is `main`. Use focused branches such as
`feat/<short-topic>`, `fix/<short-topic>`, `docs/<short-topic>`,
`test/<short-topic>` or `chore/<short-topic>` (for example,
`docs/offline-checklist`). Keep one coherent task per branch/PR.

Describe the problem and resulting behavior, scope, actual validation and known
limitations. Include UI screenshots for meaningful UI changes and API examples
for contract changes. Call out configuration or dependency changes. Link an issue
when one exists; do not require an issue for every small change. Matthew owns
integration/code review; James and Lawrence coordinate shared frontend work.

## Integration workflow

1. Coordinate file ownership and API contracts before overlapping changes.
2. Start from current `main`, inspect the code, and implement the smallest complete
   change on a focused branch. Keep lockfiles with deliberate dependency changes.
3. Update types, tests and affected documentation together. Run relevant checks
   and review the diff for generated/private files.
4. Open a PR for review; report blocked or skipped checks. Incorporate feedback,
   refresh against `main`, and resolve conflicts without discarding others' work.
5. Rerun checks affected by conflict resolution. Matthew integrates reviewed work;
   Gracianne verifies the integrated result and records QA evidence independently.

These are review practices; there is no CI pipeline, automated merge gate or
deployment configuration in this repository. Do not invent one in reporting.

## Testing expectations

From `frontend/`, run `npm run typecheck` and `npm run build` (build also runs the
type check). No frontend automated test runner currently exists. Verify important
UI interactions manually; introduce focused behavioral tests when frontend
behavior changes, with an appropriate minimal test setup if needed.

From `backend/`, use virtual-environment Python to run
`-m unittest discover -s tests -v` and `-m pip check`. On Linux the executable is
`.venv/bin/python`; on Windows it is `.\.venv\Scripts\python.exe`. Add/update
behavioral tests when changing schemas, routes, calculations or persistence.
Mock Ollama for deterministic failure/contract tests; verify real inference
separately without asserting exact generated wording.

For desktop inference/persistence/connectivity changes follow
[OFFLINE_TESTING.md](OFFLINE_TESTING.md). PWA retirement is Phase 1 cleanup, not a
product feature. Only Matthew uses Codex CLI; ownership is in [TEAM](TEAM.md).
For documentation changes check paths, links, command working directories and
claims against the implementation. Record OS/tool versions, actual results and
failures. Distinguish automated mocks, infrastructure probes and real end-to-end
tests; never infer Windows/mobile compatibility from a Linux test.
