# P0 desktop frontend plan

Proposed screens/components, not implemented files. Reuse current React Router,
TypeScript strict checking, Tailwind/Vite and API helper patterns. Source PRD
§6/§13/§15; [API_CONTRACT](API_CONTRACT.md) is authoritative for public types.

## Screens and navigation

| Route | Screen | Owner / minimum behavior |
| --- | --- | --- |
| `/` | Home/check-in | Lawrence: goal/time/energy, optional deadline/notes, at most one follow-up, ready/generate flow. |
| `/questlines/:id` | Selected active dashboard | James: current quest/actions, criteria/time/difficulty, XP/level/progress, history access, paused/completed states. |
| `/questlines` | Saved questlines/basic progress history | James: bounded metadata list, select line, profile XP/level, plain completed history in detail. |

No Quest Journey component/graph/locked milestone list in P0. No game world,
avatar, rewards, streaks, leaderboard or mandatory login. Keep responsive desktop
layout and keyboard operability; mobile inference is not a claim.

## Components and file ownership

Proposed under existing `frontend/src/`:

| Area | Components/files | Owner |
| --- | --- | --- |
| pages | Home.tsx (convert existing), QuestDashboard.tsx, SavedQuestlines.tsx | Lawrence Home; James dashboard/list |
| components | CheckInForm, FollowUpQuestion, ReplanForm, AssistancePanel, LoadingState, ErrorNotice | Lawrence |
| components | QuestCard, QuestActions, XPDisplay, ProgressSummary, QuestlineList, CompletedHistory | James |
| hooks | useQuestline, useProfile, local UI request/cancellation hooks | James; Lawrence coordinates adapters rather than duplicate hooks |
| lib | api.ts and new shared questTypes.ts if needed | James primary; Matthew approves contract; Lawrence changes by coordination |
| shared shell | App.tsx, main.tsx, styles.css, config/package | James primary; Matthew alone coordinates Phase 1 PWA cleanup |

PascalCase `.tsx`, use-prefixed hooks, explicit DTO/prop types, type-only imports.
Keep components small; no global state library needed. Do not create these files
in Phase 0. See [TEAM](TEAM.md) for review/merge boundaries.

## Check-in interaction

Typed numeric minutes (integer 1–1440), enum energy and free text. A datetime-local
input must be converted to an offset-bearing timestamp (e.g. Date.toISOString());
show the user's local deadline, including past dates, without marking failure.
Optional notes/deadline stay optional. Label energy as self-reported capacity, not
a diagnosis. Show the one server question inline; answer uses its check-in ID and
revision. Keep form data on recoverable failure. No automatic repeated questioning,
no extra clinical form. Once ready, explicitly generate; never double submit.

## Dashboard interaction

Always show goal, total/completed progress, total XP and backend-derived level.
Current QuestCard shows title/action/original criteria/estimated minutes/difficulty/
reward. Complete is explicit; optionally ask a concise confirmation that the
observable criterion is met, without AI grading. Hint and smaller starting action
are labelled assistance, not progress/replacement completion criteria.

Use separate hint/shrink/replan loading states and actionable errors. Replan form
asks updated time/energy plus optional deadline/notes/reason. Paused dashboard
keeps current quest visible and disables complete/AI actions; show Resume.
Completed line shows completed history and progress; no invalid Resume/Replan.
CompletedHistory is plain readable rows, not P1 Journey. No hidden future content
is placed in the DOM, tooltips, serialized client state or developer debug panels.

## State and API integration

Use React state/hooks and Router parameters; backend is authoritative. The route
is selected line identity; an optional localStorage **opaque selected ID only**
may improve navigation, but no goals/notes/prompts/quest plans in browser persistence.
On load fetch profile + selected line/saved summaries. 404 stale selected IDs return
to saved list, not a blank screen. Accepted assistance persists on the server.

- Generate one crypto.randomUUID Idempotency-Key per new mutating intent except
  complete; retain it for explicit retry after timeout/lost response. Editing the
  intent creates a new key. Completion naturally retries by quest ID.
- Send expected_revision from the current committed view. Refetch on 409 stale
  state before presenting another action; do not reuse an edited body under an old
  key. Pending duplicate shows Retry-After; no background offline queue.
- Never optimistically award XP/unlock/supersede. Replace views with committed
  mutation responses; completion returns profile and line. Refresh profile/list
  as needed. Replan may change total_count; explain updated plan rather than fixed
  original denominator.
- Abort abandoned reads/AI requests; ignore responses for a different selected
  ID or older revision. Serialize dashboard action UI while an intent is pending;
  backend still handles two-tab/concurrent requests safely.
- Extend API helper to parse the new error envelope, keep legacy detail support
  during rollout, use operation-specific timeouts and no-store. Handle non-JSON
  errors/network disconnects without showing raw server traces.
- Backend/DB readiness and Ollama readiness are separate. AI-down must not disable
  completion, saved reads or pause/resume. navigator.onLine is informational, never
  a condition that blocks localhost requests when internet is disconnected.

## Accessible, recoverable states

Labels, visible focus, keyboard forms/buttons, readable contrast and cues beyond
color. Announce pending/results with appropriate aria-live/aria-busy and errors
with an alert. Prevent duplicate-click UX, keep user input on errors, allow retry
and explicit return to saved work. Support empty list, first load, all-completed,
paused, stale state, model unavailable, schema failure, timeout and storage failure.
Respect reduced motion; animation is unnecessary for P0.

## Phase 1 and integration gates

First remove legacy PWA registration/cache/update notices and types/config safely,
not the entire frontend. Verify localhost origin and no active service worker.
Build static assets locally; leave preview server running for desktop offline demo.
Then establish API types before James/Lawrence split pages. Integrate the smallest
check-in→current quest→complete/XP loop before adaptive UI. Tests must verify user
flows and no locked-data DOM exposure, not just copied component implementation.
Existing type/build scripts are available; a frontend behavioral test runner is
not installed. Select a minimal setup in an authorized implementation phase or
record manual browser cases honestly; do not claim automated UI coverage exists.
