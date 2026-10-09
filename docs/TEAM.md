# Team ownership and integration boundaries

Local AI Quest Companion, P0. Four team members; **only Matthew uses Codex CLI**.
Assignments follow the locked team split and PRD §14/§16–19, not its generic role
suggestion. No implemented feature or completed demo readiness is implied.

| Member | Responsibility | Primary file/area ownership |
| --- | --- | --- |
| Matthew — technical lead/backend/integration | FastAPI, SQLAlchemy/SQLite, Ollama, quest state engine, API contracts and end-to-end integration; Codex CLI | backend/app/**, backend/tests/**, backend configuration/dependencies; AGENTS.md; API_CONTRACT, DATABASE_DESIGN, AI_DESIGN, QUEST_RULES, DECISIONS; shared contract review |
| James — primary frontend/demo | React structure, main dashboard, quest actions, XP/progress, saved lines; Windows laptop and live demo | App.tsx, main.tsx, QuestDashboard/SavedQuestlines pages; QuestCard/QuestActions/XPDisplay/ProgressSummary/List/History; hooks and lib types/API primary owner; frontend config/package after Matthew's Phase 1 cleanup |
| Lawrence — secondary frontend/UX | Check-in, loading/errors, hint/shrink/replan interaction panels, responsive desktop styling and pitch support | Home.tsx conversion; CheckInForm/FollowUpQuestion/ReplanForm/AssistancePanel/LoadingState/ErrorNotice; styling additions coordinated with James |
| Gracianne — documentation/QA/submission | PRD consistency, test scenarios/acceptance checklist, actual offline evidence, AI/tool disclosures, submission docs and demo support | OFFLINE_TESTING, AI_DISCLOSURE, documentation consistency/acceptance records; TEAM/CONVENTIONS; roadmap QA portions; submission/pitch evidence |

Proposed product paths in [FRONTEND_PLAN](FRONTEND_PLAN.md) do not yet exist.
Matthew owns architecture decisions/contracts; Gracianne reviews their consistency
with the source PRD. README/ARCHITECTURE/P0_IMPLEMENTATION_PLAN are coordinated
shared docs: one editor at a time, Matthew integrates reviewed changes.

## Collaboration boundaries

- James and Lawrence share frontend delivery, with explicit file ownership to
  reduce collisions. Lawrence's panels accept typed props/callbacks; James owns
  the shared dashboard action controller/API wiring. Do not independently build
  duplicate API clients or modify App.tsx/api.ts simultaneously.
- Agree request/response types and component callbacks first; Matthew signs off
  contract changes. Backend schemas and frontend types must change in the same
  integration sequence. Synthetic fixtures may unblock UI work, but do not count
  as real AI/offline acceptance evidence.
- Matthew coordinates PWA retirement and configuration/lockfile changes in Phase 1;
  James reviews browser cleanup/localhost operation on the demo laptop. Preserve
  ordinary local assets and existing uncommitted work.
- Work in focused feat/fix/docs/test/chore branches from main; announce shared-file
  edits, review diffs before integration, and resolve conflicts without overwriting
  teammates' changes. No automated commit/push or new CI is assumed.
- Only Matthew runs Codex CLI; other members' tools are their choice and must be
  disclosed if actually used. No private check-in data in development prompts/logs.

## Independent documentation and QA deliverables

Documentation must accurately distinguish current code from planned features.
QA independently defines and runs FR-01–FR-09 and the state/offline cases, records
outputs/timings/errors on the actual laptop and reports failed/blocked tests.
Developer mock tests are not an automatic QA sign-off. Gracianne owns evidence,
license/tool verification and official submission-page confirmation; the team
supplies versions, digests, pre-existing-code provenance and actual test results.

James rehearses live operation and manual model switch; Lawrence supports the
five-minute pitch narrative (duration is team-provided PRD guidance, verify rules).
Replace the PRD's P1 Journey demo moment with plain completed history/progress for
P0. Matthew is the owner of the full check-in→quest→complete→XP→replan demo path.

## Integration gates

Follow [P0_IMPLEMENTATION_PLAN](P0_IMPLEMENTATION_PLAN.md). First real end-to-end
loop precedes adaptation polish. James confirms Windows service/model readiness
in Phase 1; Matthew proves state/AI contracts; Lawrence delivers accessible UX;
Gracianne records Phase 5 offline/restart/error proof. Stop adding features at the
agreed internal freeze and reserve time for disclosures/rehearsal/upload.
