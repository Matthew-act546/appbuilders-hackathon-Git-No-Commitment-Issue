# Sibol demo readiness

Current follow-up to the October 10, 2026 handoff and the historical Linux
[Phase 5A report](PHASE_5A_QA_REPORT.md). This separates the user's Windows/QA
confirmations from developer automation. It does not certify full PRD completion.

## User-reported Windows and QA results

The user confirmed the following during this workspace session:

| Area | Reported result |
| --- | --- |
| Windows installation and startup | Working and verified. |
| Demo model selection | Primary `qwen3:4b`; manual fallback `qwen3:1.7b`. |
| Generated AI response quality | Passed the team's QA tester. Exact prompts, timings and a paired model comparison were not supplied. |
| Offline operation | Tested successfully; the user subsequently confirmed restarting Ollama, FastAPI and the frontend while disconnected, then generating a new questline. |
| Existing UI work | QA accepted the work through the completed-stage Journey timeline. |

These confirmations update the handoff's pending Windows/AI/offline status.
They are user-reported evidence, separate from mocked tests and earlier Linux
benchmarks. No exact hardware/driver/model-digest/latency values are inferred.

## Frontend replanning status

The user chose frontend replanning as the next priority. My Quests now exposes
the existing backend replan operation through Adjust your pace. It changes
unfinished stages only, accepts updated time/energy and an optional explanation,
and preserves completed records/XP. The original saved goal, deadline and notes
remain unchanged. See [frontend behavior](FRONTEND_PLAN.md#user-facing-replanning).

The new replan controls still need the team's live-model/manual QA walkthrough.
The previous QA approval preceded this integration and is not extended to it
automatically. Use a fictional goal, complete one stage, replan, and verify the
same completed record/earned XP, new current stage and persistence after refresh.

## Developer verification for frontend replanning

Executed on Windows, October 10, 2026, using fictional inputs and temporary SQLite:

| Check | Result |
| --- | --- |
| Frontend `npm run build` (includes typecheck) | PASS |
| Native frontend tests, Node 22 TypeScript stripping | PASS: 14/14 |
| Backend `python -m unittest discover -s tests -v` | PASS: 163/163 |
| Backend `python -m pip check` | PASS |
| Browser `node tests/core-flow.mjs`, Opera GX | PASS: 40/40 with mocked Ollama |
| Desktop/narrow form and loading-popup screenshots | Visually inspected |
| `git diff --check` | PASS |

Replan cases cover no-write validation, paused/completed guards, duplicate-submit
protection, failures preserving the previous plan, exact retries and Retry-After,
one remaining stage after completed history, lost committed responses, stale
revisions, explicit edits with new request keys, refresh and route cleanup.
History, earned XP and the saved deadline remain intact. These checks do not
extend earlier live-model QA approval to the new replan controls.

## Next handoff step

Project/demo documentation now includes the [Windows demo guide](DEMO_GUIDE.md),
updated [README](../README.md), [AI disclosure](AI_DISCLOSURE.md) and
[offline checklist](OFFLINE_TESTING.md). Reviewed
[synthetic UI screenshots](screenshots/sibol-ui/README.md) are available in the
repository. Their fictional mocked-Ollama content is separate from live QA.

The existing UI/replan work and screenshot documentation are committed and pushed
to `sub`. This project/demo documentation update remains local and uncommitted;
no pull request or submission was created by this session.

Remaining Phase 6 preparation:

- [ ] Complete live-model frontend replanning QA: preserve completed history/XP,
  inspect replacement usefulness, and verify refresh persistence.
- [ ] Record demo-machine hardware, runtime versions, installed model digests,
  actual latency and errors; do not infer them from the model tag.
- [ ] Rehearse the live walkthrough and manual fallback on the intended laptop.
- [ ] Verify licenses/source provenance and official submission/disclosure rules.
- [ ] Confirm the final submitted artifact and portal receipt when authorized.

Remaining limitations to disclose or resolve:

- Hint/shrink controls and their backend operations remain unimplemented;
  FR-04 is not complete. Advanced Progress is still a foundation.
- AI output quality can vary; QA approval is not a guarantee of universal
  requirement coverage or optimal stage count.
- Exact installed artifact/licenses, source licensing, official submission rules
  and submission confirmation remain to be recorded during Phase 6.

No user database, model weights, environment contents or private check-in text
belongs in public evidence or source control. Keep demo/evaluation inputs fictional.

Documentation-only verification: source consistency reviewed, 104 local links
resolved, 11 PowerShell code blocks parsed without syntax errors, and
`git diff --check` passed. Command examples were parsed, not executed. The earlier
application tests were not rerun for these documentation edits; no new live-model,
license or submission result is claimed.
