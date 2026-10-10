# Sibol UI review evidence

These screenshots come from the October 10, 2026 Opera GX browser regression run
of `frontend/tests/core-flow.mjs` (40/40 cases passed). The harness used fictional
goals, mocked Ollama and a temporary SQLite database. No user database or private
check-in data is included. These images demonstrate UI behavior; they do not
establish real-model quality or offline readiness.

- [Saved questlines](saved-questlines-scroll-desktop.png): aligned panel borders,
  independent list scrolling and Sibol branding.
- [Completion popup](completion-popup-desktop.png): centered modal and blurred
  background. This capture exercises a replay, so it correctly shows zero
  additional XP rather than awarding the same completion twice.
- [Journey timeline](journey-timeline-desktop.png): completed history, saved stage
  details and campaign XP.
- [Replan form](replan-form-desktop.png): time/energy controls, optional explanation
  and validation feedback. The validation message remains after correcting the
  input until the next submission.
- [Replan loading popup](replan-loading-popup.png): energy-aware encouragement
  while replacing unfinished stages.

Blue outlines show keyboard focus during accessibility checks. See
[demo readiness](../../DEMO_READINESS.md) for validation and remaining live QA.
