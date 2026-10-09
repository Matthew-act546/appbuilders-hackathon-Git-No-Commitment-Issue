# Local AI Quest Companion agent instructions

## Authority and current phase

System/developer instructions precede explicit user instructions, then applicable
directory AGENTS.md files, then supporting docs. Read the complete
[final PRD v2.0](docs/Local_AI_Quest_Companion_Final_PRD.docx), [README](README.md),
[DECISIONS](docs/DECISIONS.md), and relevant contracts before changing anything.
The PRD supersedes AralSpace/CampusPilot; user-locked implementation decisions
resolve its open details. Distinguish implemented code from proposed behavior.

Phase 0 is documentation only. Do not install dependencies, create models/tables
or migrations, remove PWA code, refactor source, commit or push. Preserve existing
uncommitted work. Begin each future session with Git status and a scoped code/doc
audit; implement only the phase explicitly authorized by Matthew.

## Product and architecture

- P0: capacity-aware check-in → 2–6 meaningful stages → one current quest per
  active questline → explicit completion/XP/unlock → hint/shrink/replan/pause/resume
  → saved history and restart-safe progress. Multiple saved questlines are allowed;
  the UI focuses on one selected line.
  Approved post-PRD adaptive sizing: AI chooses the smallest useful count for the
  complete goal, possibly across sessions; no classification call or filler.
  Replans preserve history and cap completed plus replacement stages at six;
  one remaining stage is allowed once history supplies another stage. See
  [DECISIONS](docs/DECISIONS.md).
- Desktop web app, **not PWA**, on one laptop. React/TypeScript/Vite/Tailwind →
  Python 3.11+/FastAPI/Pydantic/SQLAlchemy/SQLite + HTTPX/Ollama. React Router and
  Pydantic Settings are reusable scaffold infrastructure. Phase 1 removes legacy
  PWA behavior safely; Phase 0 leaves it intact.
- Local origins: frontend `http://localhost:5173`, backend
  `http://127.0.0.1:8000`, Ollama `http://127.0.0.1:11434`. Configure through the
  existing environment variables. Core inference stays local; no cloud services,
  remote AI API, mandatory accounts/authentication, CDN runtime assets or mobile
  inference claims. Offline means internet disconnected while local servers work.
- Keep application endpoints under `/api`; `/api/health` is canonical. Follow
  [API_CONTRACT](docs/API_CONTRACT.md), not raw ORM serialization.
- AI suggests content/difficulty only. Backend assigns IDs, sequence, status,
  versions and XP. Easy=10, medium=20, hard=30; level=`total_xp // 100 + 1`.
  Never delegate state, XP, date validation or arithmetic to an LLM.
- Validate strict structured output before saving. One bounded malformed-output
  retry; manual model switching only (`qwen3:1.7b` / `qwen2.5:1.5b`). Do not claim
  compatibility or benchmark results until measured on the actual demo laptop.
- Enforce single-current-quest, unique completion and transactional XP in SQLite
  plus backend services. Generate replacements outside write transactions;
  validate and compare revision before atomically replacing unfinished work.
  Completed records/XP are immutable under replan. Hide locked/superseded content
  through every public response. See [QUEST_RULES](docs/QUEST_RULES.md).
- No medical diagnosis, therapy or treatment. Use supportive, non-coercive language;
  hints/shrinking do not complete quests and missed deadlines carry no penalties.

## Change discipline and conventions

Inspect/reuse established patterns. Make small changes, coordinate shared files,
and follow [CONVENTIONS](docs/CONVENTIONS.md) and [TEAM](docs/TEAM.md). Keep typed
modular React components, accessible controls and loading/recoverable errors.
Use Pydantic for API/model boundaries and SQLAlchemy for persistence. Treat model
text as untrusted text, never executable HTML/code/SQL. Keep schema/domain checks
deterministic. Do not add P1 Quest Journey, P2 rewards, game worlds or deferred work.

Use environment configuration and safe `.env.example` values; `VITE_*` values are
public. Never expose actual environment contents, credentials, keys or private
check-ins in logs/docs/source control. Never commit `.env`, databases/WAL files,
model weights, dependencies, virtual environments or generated build/cache files.
No raw sensitive prompt/output logging. Use synthetic QA/demo data.

## Definition of done

- Requested phase/scope complete; code, API types, schemas and docs agree.
- Add/update behavioral tests for state, persistence and contract changes. Test
  duplicate/concurrent completion, rollback, replan failure/staleness, paused
  behavior and public response filtering, not just happy paths.
- Run relevant existing checks from the app directory: frontend
  `npm run typecheck` / `npm run build`; backend virtual-environment Python
  `-m unittest discover -s tests -v` / `-m pip check`. No lint/UI runner currently
  exists. Use [OFFLINE_TESTING](docs/OFFLINE_TESTING.md) for real demo validation.
- Documentation-only work checks source coverage, links, commands, contracts and
  consistency without implementing features. Review diff/status and preserve
  unrelated work. Report actual checks, skipped checks/reasons and remaining risks.
- Do not infer benchmark, Windows, offline or restart success from mocked tests.
  Never invent results or continue to the next phase automatically.
