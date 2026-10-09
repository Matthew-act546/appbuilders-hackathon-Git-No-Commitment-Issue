# Local AI Quest Companion — Design System

**Status:** Phase 4 implementation specification  
**Design direction:** Cozy forest · friendly minimalism · playful utility  
**Target:** Desktop-first browser application, offline-capable, no PWA  
**Source:** Team-provided palette and Home / check-in / quest / progress visual references  
**Related:** `FRONTEND_PLAN.md`, finalized PRD, `docs/API_CONTRACT.md`

## 1. Design principles

1. **One small step at a time.** The current actionable quest is visually dominant; avoid overwhelming the user with future work.
2. **Calm, not clinical.** Warm colors, approachable copy, friendly mascot, and ample whitespace. Avoid claims about mental-health treatment or outcomes.
3. **Playful but trustworthy.** Rounded shapes and subtle offset shadows coexist with clear controls, explicit status, and honest AI failures.
4. **Accessible and legible.** Strong text contrast, visible keyboard focus, readable sizing, and no color-only status signaling.
5. **Offline by design.** All fonts, icons, and illustration assets are bundled locally. No runtime CDN, external image calls, or telemetry.
6. **Real state, never decorative fiction.** XP, levels, quest status, completion history, and local model status come from backend responses; screenshots' sample values are not application defaults.

## 2. Color tokens

The following HEX values are **approved brand colors** from the team's reference. Do not substitute near matches.

| Token | HEX | Primary use |
|---|---|---|
| `--color-cream` | `#FFF9ED` | Main app canvas and warm input backgrounds |
| `--color-sage` | `#B9D99A` | Primary buttons, active navigation, positive banners |
| `--color-butter` | `#FFE99A` | XP/level chips, current quest emphasis, highlights |
| `--color-leaf` | `#78B96A` | Secondary decorative accents, foliage, icon accents |
| `--color-ink` | `#29231F` | Primary text, borders, icons, strong shadows |
| `--color-white` | `#FFFFFF` | Navigation, content cards, form surfaces |

**Supporting colors (proposed; adjust after browser contrast checks):**

| Token | HEX | Use |
|---|---|---|
| `--color-muted-text` | `#6C625B` | Secondary text on cream/white |
| `--color-pale-leaf` | `#EDF5E2` | Quiet secondary panels |
| `--color-pale-butter` | `#FFF6D0` | Active quest background |
| `--color-divider` | `#D9CDBD` | Soft separators and input borders |
| `--color-danger` | `#9B3434` | Error text and critical status |
| `--color-danger-bg` | `#FFF0EE` | Recoverable error panels |
| `--color-focus` | `#285F9C` | Keyboard focus outline, distinct from green |

### Contrast and usage rules

- Use **ink** for body text on cream, white, sage, butter, and pale surfaces.
- Do **not** use white text on sage, leaf, or butter as a default: contrast may be insufficient.
- Never convey error, locked, complete, paused, or active state with color alone; use labels and icons.
- Verify WCAG AA contrast in the implemented browser: 4.5:1 for normal text and 3:1 for large text and relevant controls.
- Leaf green is an accent, not the default small-text color.

### CSS variable starter

```css
:root {
  --color-cream: #FFF9ED;
  --color-sage: #B9D99A;
  --color-butter: #FFE99A;
  --color-leaf: #78B96A;
  --color-ink: #29231F;
  --color-white: #FFFFFF;
  --color-muted-text: #6C625B;
  --color-pale-leaf: #EDF5E2;
  --color-pale-butter: #FFF6D0;
  --color-divider: #D9CDBD;
  --color-danger: #9B3434;
  --color-danger-bg: #FFF0EE;
  --color-focus: #285F9C;
}
```

## 3. Typography

**Visual target:** Friendly, rounded, readable sans-serif resembling the screenshots. Font identity has **not** been confirmed; do not assert an exact screenshot font.

- Prefer a locally bundled, appropriately licensed rounded sans-serif **if already available**; otherwise use a system stack: `ui-rounded, "Trebuchet MS", "Segoe UI", system-ui, sans-serif`.
- Headings: 700–800 weight, compact tracking, ink.
- Body: 400–500 weight, generous line-height (1.5–1.65).
- Labels/buttons: 600–700 weight.
- Desktop scale (suggested): hero 36–44px; page title 30–36px; section 22–26px; card title 20–24px; body 16px; helper 14px; metadata 12–13px.
- Never use tiny text for completion criteria or form instructions. Keep minimum meaningful content around 14px.

## 4. Layout and responsive behavior

- Desktop-first target: **1280–1600px** viewport, including the Windows demo laptop.
- Main content max width: **1160–1200px**; centered with 24–32px desktop gutters.
- Top bar: white, ~76–88px high, thin ink bottom border; brand left, four nav links centered, level/XP and settings right.
- Desktop check-in: centered form card, approx. **560–640px** max width.
- Quest workspace: **two-column** layout with dominant active quest card and narrower journey/replan sidebar; stack vertically below ~960px.
- At widths below ~760px, wrap/collapse nav into an accessible menu; preserve full feature access even though mobile is not the primary demo target.
- Spacing scale: `4, 8, 12, 16, 24, 32, 48, 64px`.
- Content must remain usable at 200% browser zoom without clipped controls or horizontal overflow.

## 5. Shape, border, and elevation

- Cards: white or pastel surface; **2px ink outline** for prominent cards; **16–20px radius**.
- Primary buttons: sage fill, 2px ink border, 10–12px radius, **3–4px hard offset ink shadow** where appropriate.
- Large feature cards: optional 4–5px bottom-right hard shadow. Avoid stacking multiple heavy shadows.
- Inputs: white/cream fill, 1px muted border, 10–12px radius; focused outline visible.
- Pills/badges: butter fill, ink outline, rounded-full or 8px radius.
- Dividers: subtle divider token, never dark outlines everywhere.
- Keep visual depth consistent: primary active quest > support panels > metadata.

## 6. Components

### 6.1 AppHeader / Navigation

- Brand: small original forest mascot or sprout icon, **Local AI** title, **Quest Companion** subtitle.
- Links: **Home**, **My Quests**, **Journey**, **Progress**. The active link has sage fill and ink outline; inactive links use simple icons and muted text.
- Logo returns to Home.
- Right area: actual backend level and total XP; settings icon opens local app/model settings/status.
- Keyboard-accessible links, visible focus, `aria-current="page"` on active link.
- Do not show fictional level/XP before profile loads; show skeleton or a neutral loading state.

### 6.2 WelcomeHero

- Cream canvas, centered heading and supportive subheading; small butter eyebrow badge.
- Decorative pale leaf and butter shapes may be used sparingly.
- Forest mascot near the hero, but keep goal form the focal point.
- Sample tone: “One small step at a time.” Avoid promises of productivity outcomes.

### 6.3 CheckInCard

- White card, bold ink border, rounded corners.
- Goal textarea with examples; available minutes selector/input; energy choice **Low / Medium / High**; optional deadline.
- Screenshot label “Steady” is visual reference only; map displayed options explicitly to backend enum values.
- Primary CTA: **Start my journey**; disable repeated submits while an operation is pending.
- Inline validation and draft retention after errors/reload when supported by backend check-in state.

### 6.4 ClarificationCard

- Display exactly one backend-provided clarification question at a time.
- Preserve original goal visibly in condensed form.
- Text input and clear CTA: **Continue**.
- Never invent an answer; handle insufficient answers without losing the question.

### 6.5 ActiveQuestCard

- Pale butter background; dark border and offset shadow; active badge and `Quest X of N` indicator.
- Visible: title, concrete action, completion criteria, estimated minutes, difficulty, XP reward **from backend-owned rules**, and optional hint.
- Primary CTA: **Complete quest**; secondary: **Get a hint**, **Make it smaller** (only when supported), and pause/replan in a nearby panel.
- Confirm completion only after backend success; no optimistic XP credit.
- Preserve distinction between **difficulty** and **XP**. Screenshot `+30 XP` next to a “small step” is not authoritative.

### 6.6 JourneyPreview / JourneyMap

- Connected nodes for completed, current, and locked quests.
- **Never render locked quest titles, actions, hints, or criteria.** Show only neutral locked nodes and permitted counts/position information returned by the API.
- Completed nodes: checkmark; active node: flag/sprout; locked: lock. Use labels, not color alone.
- Keep simple horizontal preview in workspace; larger accessible vertical/horizontal view on Journey page.

### 6.7 ReplanPanel

- Pale leaf background; selects for revised available minutes and energy, and **Replan** CTA.
- Explicitly explain that completed quests and XP are preserved.
- Pending, stale-revision, and model-unavailable states must be understandable and recoverable.

### 6.8 ProgressCards

- Three main cards: **Total XP** (white), **Current Level** (butter), **Completed Quests** (pale leaf).
- XP to next level is calculated from backend total XP with the agreed rule, unless the API supplies it.
- Show actual completed history; handle zero progress without invented data.

### 6.9 Status and feedback

- Success banner: sage surface, ink icon/text, dismissible where appropriate.
- Loading: explicit “Generating quests locally…” message; show that this can take several seconds. Avoid fake percent progress.
- Recoverable errors: pale danger surface, meaningful message, Retry/Revise goal action.
- Model missing/Ollama unavailable: show actionable local setup guidance; do not claim offline AI is running.
- Semantic rejection: “This plan needs a little more detail” with revise/clarify/retry paths. Do not silently persist or display an unaccepted plan.
- Empty saved questlines: invite user to start at Home.

## 7. Mascot, icons, and imagery

- Reference style: tiny, soft-green forest creature with leaf-like ears, simple face, dark brown outline, and cream belly.
- Treat reference screenshots as **inspiration**, not permission to extract or redistribute a proprietary illustration.
- Use an **original team-created or properly licensed** mascot. Provide SVG/PNG locally in `frontend/src/assets/` with license/source note where required.
- Use consistent outline icons (e.g., locally bundled `lucide-react` if already in dependencies; do not add a network icon library).
- No animated mascot is required for P0. If animation is used, respect `prefers-reduced-motion`.

## 8. Motion and interaction

- Hover: slight elevation or background shift, no layout jump.
- Press: shadow compresses to reinforce tactile feel.
- Motion duration: ~120–200ms for simple transitions; optional, not critical-path.
- Respect `prefers-reduced-motion`.
- Every action has a disabled/pending/error state; prevent accidental double submits.
- Do not use celebratory effects until the backend confirms completion.

## 9. Accessibility and content

- Semantic landmarks: `header`, `nav`, `main`; one H1 per page.
- Labels are always visible; placeholders are examples, not labels.
- Buttons have clear accessible names; icon-only settings button has `aria-label`.
- Focus visible; keyboard can reach all controls and dismiss dialogs.
- Announce asynchronous results and validation errors using appropriate live regions.
- Touch/click targets ideally at least 44×44px.
- Tone: warm, concise, non-judgmental. Avoid guilt, urgency theater, medical framing, and “AI knows best” messaging.
- Disclose that quest suggestions come from a **local AI model** and may need user review.

## 10. Design QA acceptance checklist

- [ ] All six approved brand HEX colors used exactly.
- [ ] Four nav sections have distinct destinations and active states.
- [ ] Home, My Quests, Journey, Progress visually match the reference direction.
- [ ] Current quest dominates; locked content stays hidden.
- [ ] XP and level reflect backend state only.
- [ ] Check-in, clarification, loading, semantic rejection, and retry are styled.
- [ ] All fonts, icons, mascot, and CSS work with internet disconnected.
- [ ] Keyboard navigation, focus, contrast, and reduced motion verified.
- [ ] Desktop demo laptop viewport and narrower browser widths tested.
- [ ] No hardcoded mock demo content in production screens.

## 11. Decisions still requiring team confirmation

- Final **font family** and local license/asset source.
- Original **mascot asset** (reference is not automatically reusable).
- Whether to display the screenshot's dismissible green announcement banner globally or only after successful generation.
- Whether settings is a small dialog or a dedicated page; prefer a dialog for P0.

These are visual choices, not blockers to building the working P0 flow.
