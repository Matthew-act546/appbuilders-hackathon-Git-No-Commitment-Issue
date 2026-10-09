"""Optional model copy: bounded, quest-specific wording without new factual claims.

Only completion of this exact title is asserted. A small allowlist of supportive
tails avoids inventing learning outcomes or leaking another stage's content.
Invalid copy is discarded, never a reason to reject a quest proposal.
"""
import re

TAILS = (
    "Let this small step be a quiet win along your path.",
    "Take a breath and enjoy this little clearing in the forest.",
    "Keep moving at your own pace, one small step at a time.",
    "A little forest cheer for the effort you chose to give.",
)


def excerpt(value: str, limit: int) -> str:
    first = re.split(r"[.!?]\s+", value.strip(), maxsplit=1)[0].rstrip(".!?")
    words = first.split()
    label = " ".join(words[:limit])
    shortened = len(words) > limit or len(label) > 80
    return label[:80].rstrip(" ,;:.!?") + ("…" if shortened else "")


def contextual_prefix(title: str, action: str) -> str:
    return f'“{excerpt(title, 6)}” is complete—your step: “{excerpt(action, 8)}”.'


def safe_encouragement(value: object, title: str, *, action: str = "") -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if len(value) > 500 or len(value.split()) > 35:
        return None
    prefixes = (f'You completed “{title}”.', f'You completed "{title}".',
                f'“{title}” is complete.', f'"{title}" is complete.')
    if action:
        prefixes += (contextual_prefix(title, action),)
    return value if value in {f"{prefix} {tail}" for prefix in prefixes for tail in TAILS} else None


def completed_encouragement(title: str, value: object, *, action: str = "") -> str:
    safe = safe_encouragement(value, title, action=action)
    # A safe model-selected ending can vary the tone, while the backend grounds
    # the final message in an exact excerpt of this quest's permitted action.
    tail = next((tail for tail in TAILS if safe and safe.endswith(tail)), TAILS[0])
    if action:
        return f"{contextual_prefix(title, action)} {tail}"
    if safe:
        return safe
    # Legacy quests need no inference or database mutation. Bound unusually long
    # titles while retaining their specific identity in the visible quest card.
    words = title.split()
    label = " ".join(words[:12]) + ("…" if len(words) > 12 else "")
    return f'You completed “{label}”. {tail}'
