"""Conservative checks for known violations, never a semantic relevance proof."""
import re
from dataclasses import dataclass

from .errors import QuestError
from .schemas import GroundingContext, QuestlineContext, QuestPlan, SemanticReview

QUALITY_VERSION = "essential-constraints-v3d.1"
STOP = set("a an the my our your for to of in on and with basic programming project assignment presentation exam skills finish prepare improve study build write work do it something anything please i want need am im tired today tomorrow tonight".split())


def meaningful_words(value: str) -> set[str]:
    return {w.rstrip(".-") for w in re.findall(r"[a-z][a-z0-9_+.-]*", value.lower()) if w.rstrip(".-") not in STOP}


def unsupported_request(text: str) -> bool:
    return bool(re.search(r"\b(diagnos\w*|therap\w*|treat\w*)\b.{0,80}\b(depression|anxiety|mental health|disorder|trauma)\b", text, re.I))


def clarification_question(context: QuestlineContext) -> str | None:
    text = context.goal + " " + (context.contextual_notes or "")
    if unsupported_request(text):
        raise QuestError("UNSUPPORTED_REQUEST", 422, "This companion cannot provide diagnosis, therapy or treatment.")
    words = meaningful_words(text)
    if re.search(r"\b(cook\w*|make|prepare)\b.*\b(dish|meal|food|dinner|lunch|breakfast|snack|eat)\b", text, re.I):
        # A recipe must not invent food availability. A named dish or supplied
        # ingredients can proceed; a generic dish genuinely needs this one fact.
        if not re.search(r"\b(sandwich|salad|soup|pasta|rice|omelet\w*|ingredients?|bread|tomato|cheese|lettuce|eggs?|chicken|beans)\b", text, re.I):
            return "Which dish or ingredients you already have would you like to use?"
    if re.search(r"\b(assignment|homework)\b", text, re.I):
        if not re.search(r"\b(implement|debug|solve|unit tests?|essay|report|function|algorithm|requirements?[:])\b", text, re.I):
            return "What does the assignment require you to produce? Describe the relevant task and any required tools."
    elif re.search(r"\b(presentation|slides|pitch|present|presenting|introduction)\b", text, re.I):
        unknown_topic = re.search(r"\b(?:complex|unknown|unspecified|unfamiliar) topic\b", text, re.I)
        named_topic = re.search(r"\b(?:on|about|introduction to|topic is|topic:)\s+(?!a (?:complex|unknown|unspecified) topic\b)\w+", text, re.I)
        format_only = not (words - {"short", "exactly", "one", "two", "three", "four", "five", "timed", "rehearsal", "slides", "slide", "create", "minute", "minutes", "classmates", "practice"})
        if (unknown_topic and not named_topic) or (not named_topic and (len(words) < 3 or format_only)):
            return "What is the presentation topic and the main result you need to communicate?"
    elif re.search(r"\b(exam|test preparation)\b", text, re.I):
        if len(words - {"tomorrow", "tonight", "class", "upcoming"}) < 2:
            return "Which subject and topics does the exam cover?"
    elif re.search(r"\b(programming|coding) skills\b", text, re.I) and not re.search(r"\b(python|java|javascript|typescript|c\+\+|binary search|list comprehensions?|unit tests?)\b", text, re.I):
        return "Which programming topic do you want to practice using tools you already have locally?"
    elif re.search(r"\bcrud\b", text, re.I):
        if not re.search(r"\b(entity|records?|tasks?|books?|contacts?|inventory|products?)\b", text, re.I):
            return "Which records should the CRUD app manage, and which existing local stack will you use?"
    elif len(words) < 2:
        return "What specific output do you want to create, and what is its subject?"
    return None


def validate_answer(answer: str) -> None:
    if unsupported_request(answer):
        raise QuestError("UNSUPPORTED_REQUEST", 422, "This companion cannot provide diagnosis, therapy or treatment.")
    if re.search(r"\b(?:complex|unknown|unspecified) topic\b", answer, re.I) or len(meaningful_words(answer)) < 2 or answer.casefold() in {"i don't know", "not sure", "anything you like"}:
        raise QuestError("CLARIFICATION_INSUFFICIENT", 422,
                         "Please answer the existing question with a concrete task or topic. No new question has been added.")


def grounded_text(context: QuestlineContext, grounding: GroundingContext) -> str:
    # Summary is derived, not permission for new tools; only original user facts count.
    return " ".join([context.goal, context.contextual_notes or "", grounding.clarification_answer or ""])


TECHNOLOGIES = (
    r"\bpython\b", r"\bflask\b", r"\bfastapi\b", r"\bdjango\b", r"\breact\b",
    r"\b(?:javascript|js)\b", r"\b(?:typescript|ts)\b", r"\bjava\b", r"\bc\+\+", r"\bc#",
    r"\btkinter\b", r"\bnode(?:\.js)?\b", r"\bexpress\b", r"\bspring\b", r"\bphp\b",
    r"\blaravel\b", r"\brust\b", r"\bsqlite\b", r"\bmysql\b", r"\bpostgres\w*\b",
    r"\b(?:powerpoint|google slides)\b", r"\b(?:login|authentication|oauth)\b",
    r"\b(?:calculator|hello world|todo app|weather app)\b",
)
EXTERNAL = re.compile(r"https?://|\b(download|buy|purchase|shopping|sign up|signup|meetup|heroku|firebase|netlify|vercel|leetcode|codewars|hackerrank|aws|azure)\b|"
                      r"\b(online (course|challenge|tutorial|resource)|create.{0,20}account|cloud deployment|google cloud|install new)\b", re.I)
SUBJECTIVE = re.compile(r"\b(understand|understood|confiden\w*|visually appealing|works well|no major bugs|fully grasp|feel ready|smoothly)\b", re.I)
ARTIFACT = re.compile(r"\b(files?|outline|list|checklist|notes?|document|paragraph|draft|slides?|tests?|assertions?|output|result|example|trace|table|cases?|questions?|answers?|records?|endpoints?|schema|function|models?|database|code|report|summary|diagram|section|saved|written|runs?|passes?|fails?|returns?|exists?|contains?|includes?|compiled|completed)\b", re.I)
# Observable physical outcomes count too. This is a necessary concreteness
# screen, not proof of relevance/safety or a universal semantic classifier.
PHYSICAL_OUTCOME = re.compile(r"\b(ingredients?|dish|meal|sandwich|snack|plate|bowl|food|vegetables?|bread|tomato|cheese|lettuce|desk|counter|surface|area|items?|trash|storage|shelf|basket|laundry|clothes|floor)\b", re.I)
PHYSICAL_STATE = re.compile(r"\b(selected|gathered|washed|rinsed|wiped|cleared|clear|placed|sorted|stored|put away|assembled|arranged|pressed|spread|distributed|visible|prepared|served|cut|sliced|removed|returned|empty|free of|on (?:the|a)|in (?:the|a)|ready for (?:serving|consumption|use)|contains)\b", re.I)
INGREDIENTS = re.compile(r"\b(bread|tomato(?:es)?|cheese|lettuce|eggs?|chicken|beef|pork|fish|rice|flour|sugar|butter|oil|salt|milk|pasta|potatoes?|beans|onions?|carrots?|peanuts?|banana|yogurt|cucumber|tuna)\b", re.I)
HEAT = re.compile(r"\b(cook|boil|fry|bake|grill|microwave|stove|oven|heat|simmer|roast)\b", re.I)


def ingredient_name(value: str) -> str:
    word = value.casefold()
    return {"tomatoes": "tomato", "potatoes": "potato"}.get(word, word.rstrip("s"))


def positive_matches(pattern: re.Pattern, text: str):
    """Don't mistake an explicit prohibition for a required external/heat step."""
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 45):match.start()]
        if not re.search(r"\b(?:no|without|avoid|never|do not|don't)(?:[ -]+\w+){0,3}[ -]*$", prefix, re.I):
            yield match



def optional_tool_example(text: str, match: re.Match) -> bool:
    if not re.fullmatch(r"(?:python|flask|fastapi|django|react|javascript|js|typescript|ts|java|c\+\+|c#|node(?:\.js)?|express|spring|php|laravel|rust|sqlite|mysql|postgres\w*|powerpoint|google slides)", match.group(0), re.I):
        return False
    prefix = text[max(0, match.start() - 100):match.start()]
    suffix = text[match.end():match.end() + 35]
    if re.search(r"\b(must|required|download|install|sign up)\b", prefix, re.I) or re.match(r"\s+(?:is |must be )?(?:required|mandatory|only)\b", suffix, re.I):
        return False
    return bool(re.search(r"(?:\boptional|\bif (?:already )?available|\bif you already have|\be\.g\.|\bsuch as|\btool like|\beditor like|\bfor example)[^;.!?]{0,70}$", prefix, re.I))


def optional_external_suggestion(text: str, match: re.Match) -> bool:
    # Explicitly optional suggestions are not mandatory prerequisites. Never let
    # an "optional" label waive a later must/required instruction.
    prefix = re.split(r"[;.!?]", text[:match.start()])[-1]
    suffix = text[match.end():match.end() + 50]
    return bool(re.search(r"\b(?:optional(?:ly)?|if desired|you could)\b", prefix, re.I)
                and not re.search(r"\b(?:must|required|mandatory|need to)\b", prefix + suffix, re.I))


def criteria_issue(value: str) -> bool:
    # Printed/displayed program output and timed rehearsal are observable too;
    # an intention or subjective understanding remains insufficient.
    observable = (ARTIFACT.search(value) or
                  (PHYSICAL_OUTCOME.search(value) and PHYSICAL_STATE.search(value)) or
                  re.search(r"\b(?:loop|script|program|function)\b.*\b(?:prints?|displays?|outputs?|produces?)\b", value, re.I) or
                  re.search(r"\b(?:timed|recorded|completed|duration)\b.*\b(?:rehearsal|practice|delivery)\b|\b(?:rehearsal|practice|delivery)\b.*\b(?:timed|recorded|completed|duration)\b", value, re.I))
    subjective = SUBJECTIVE.search(value) or re.search(r"\b(well[- ]structured|easy to follow|ready for the presentation)\b|^(?:I )?can (?:deliver|explain|understand)\b", value, re.I)
    return bool(subjective or re.search(r"\b(?:visually clear|visually engaging|proper pacing|clear pronunciation|logical flow|formatted correctly)\b", value, re.I) or not observable)


@dataclass(frozen=True)
class RepairTarget:
    quest_index: int
    fields: tuple[str, ...]
    codes: tuple[str, ...]


REPAIRABLE_CODES = {"unobservable_criteria", "vague_action"}
REPAIR_INSTRUCTIONS = {
    "unobservable_criteria": "Replace subjective readiness/understanding with a concrete output, visible physical state or one timed run with recorded duration. Preserve the action and all user constraints.",
    "vague_action": "Name the exact local starting action contributing to the user's goal and existing completion criterion; do not invent tools or scope.",
}


def planning_requirements(context, grounding: GroundingContext | None) -> list[str]:
    supplied = context.goal + " " + (getattr(context, "contextual_notes", None) or "") + " " + (grounding.clarification_answer or "" if grounding else "")
    requirements = ["Every action must serve the supplied goal, using local resources only."]
    slide_count = re.search(r"\b(one|two|three|four|five|\d+)[ -]+slides?\b", supplied, re.I)
    if slide_count:
        requirements.append(f"Create exactly {slide_count.group(1)} slides. The slide count is not the number of quests.")
    if re.search(r"\b(practice|rehears\w*)\b", supplied, re.I) and re.search(r"\b(present\w*|slides|introduction)\b", supplied, re.I):
        rehearsals = re.search(r"\b(one|two|three|four|five|\d+) (?:timed )?rehearsals?\b", supplied, re.I)
        count = rehearsals.group(1) if rehearsals else "at least one"
        requirements.append(f"Include {count} actual aloud rehearsal using a timer and note elapsed duration in text; no mandatory audio/video recording. Do not substitute slide editing or subjective readiness.")
        speech = re.search(r"\b(\d+)[ -]minute (?:introduction|presentation|talk)\b", supplied, re.I)
        requirements.append(f"The requested speech duration is {speech.group(1)} minutes; aim for that target." if speech else "Speech duration is unspecified; measure the run without inventing a 5-minute or session-length limit.")
    count = explicit_test_count(supplied)
    if count is not None:
        requirements.append(f"Write exactly {count} tests. Inspect the local endpoint/fixtures for expected results; never assume or state numeric HTTP response codes. Keep the existing runner, no installation.")
    if re.search(r"\b(?:make|cook|prepare)\b.{0,100}\b(?:food|meal|eat|snack|sandwich|dish)\b", supplied, re.I):
        ingredients = sorted({ingredient_name(m.group(0)) for m in positive_matches(INGREDIENTS, supplied)})
        requirements.append("Prepare then assemble then serve, using only these supplied foods: " + ", ".join(ingredients) + ". No extra foods or repeated assembly. Use hands to place food, not a knife to press it.")
    if re.search(r"\b(?:clean|tidy)\b.*\bdesk\b", supplied, re.I):
        requirements.append("Clear and organize the items actually present on the desk. Do not gather a vacuum, bucket, special cloths, chemicals, new lighting or furniture that was not mentioned. A concrete cleared space is the outcome.")
    return requirements


def repair_targets(plan: QuestPlan, codes: tuple[str, ...]) -> tuple[RepairTarget, ...]:
    if not codes or set(codes) - REPAIRABLE_CODES:
        return ()  # Hard/global violations need complete correction and revalidation.
    targets = []
    seen_criteria = set()
    for index, quest in enumerate(plan.quests):
        normalized = " ".join(quest.completion_criteria.casefold().split())
        duplicate = normalized in seen_criteria
        seen_criteria.add(normalized)
        fields, reasons = [], []
        if "unobservable_criteria" in codes and (criteria_issue(quest.completion_criteria) or duplicate):
            fields.append("completion_criteria"); reasons.append("unobservable_criteria")
        if "vague_action" in codes and (len(re.findall(r"\w+", quest.action)) < 2 or re.search(r"\b(work on it|make progress|do the task|do your best)\b", quest.action, re.I)):
            fields.append("action"); reasons.append("vague_action")
        if fields:
            targets.append(RepairTarget(index, tuple(fields), tuple(reasons)))
    return tuple(targets)


NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}


def explicit_test_count(text: str) -> int | None:
    match = re.search(r"\b(one|two|three|four|five|\d+)\s+(?:unit\s+)?test(?:s| cases)\b", text, re.I)
    if match:
        value = match.group(1).lower()
        return int(value) if value.isdigit() else NUMBER_WORDS[value]
    return None


def deterministic_issues(plan: QuestPlan, context: QuestlineContext, grounding: GroundingContext) -> tuple[str, ...]:
    """Local diagnostic findings, including non-blocking quality opinions.

    Production uses essential_checks below; this fuller diagnostic pass must not
    become an acceptance gate again.
    """
    supplied = grounded_text(context, grounding)
    issues: set[str] = set()
    combined = " ".join(" ".join((q.title, q.action, q.completion_criteria)) for q in plan.quests)
    # Named literal constraints are enforceable necessary conditions, NOT proof
    # that the rest of the plan is semantically entailed by the user's context.
    for concept in (r"binary search", r"list comprehensions?", r"sqlite", r"transactions?", r"\bloops?\b"):
        if re.search(concept, supplied, re.I) and not re.search(concept, combined, re.I):
            issues.add("unrelated")
    if re.search(r"\bartificial intelligence\b", supplied, re.I) and not re.search(r"\b(?:artificial intelligence|AI)\b", combined, re.I):
        issues.add("unrelated")
    if re.search(r"\bexplanation\b", supplied, re.I) and not re.search(r"\b(explain\w*|explanation)\b", combined, re.I):
        issues.add("unrelated")
    if re.search(r"\b(presentation|slides|present|introduction)\b", supplied, re.I):
        # Explicit deliverables must survive generation; completed work satisfies
        # their coverage during replan without requiring its repetition.
        coverage = combined + " " + " ".join(q.title + " " + q.action + " " + q.completion_criteria for q in grounding.completed)
        if re.search(r"\b(practice|rehears\w*)\b", supplied, re.I) and not re.search(r"\b(practice|rehears\w*)\b", coverage, re.I):
            issues.add("unrelated")
        if re.search(r"\b(?:one|1) timed rehearsal\b", supplied, re.I):
            if not re.search(r"\b(?:timed rehearsal|time (?:the |your )?(?:rehearsal|delivery)|rehears\w*.*timer|rehears\w*.*duration|duration.*rehears\w*)\b", coverage, re.I):
                issues.add("unrelated")
            if re.search(r"\b(?:two|three|four|five|[2-9]) (?:timed )?rehearsals?\b", coverage, re.I):
                issues.add("duplicate_or_contradiction")
        count = re.search(r"\b(one|two|three|four|five|\d+)[ -]+slides?\b", supplied, re.I)
        if count:
            value = count.group(1).lower()
            expected = int(value) if value.isdigit() else NUMBER_WORDS[value]
            declared = re.search(r"\b(one|two|three|four|five|\d+)[ -]+slides?\b", coverage, re.I)
            actual = (int(declared.group(1)) if declared.group(1).isdigit() else NUMBER_WORDS[declared.group(1).lower()]) if declared else None
            ordinals = [number for word, number in (("first", 1), ("second", 2), ("third", 3), ("fourth", 4), ("fifth", 5)) if re.search(rf"\b{word} slide\b", coverage, re.I)]
            if (actual is not None and actual != expected) or (actual is None and max(ordinals, default=0) != expected):
                issues.add("duplicate_or_contradiction")
    requested_count = explicit_test_count(supplied)
    if requested_count is not None:
        writing = " ".join(q.action + " " + q.completion_criteria for q in plan.quests
                           if re.search(r"\b(write|create|add|implement|develop|record|document|run|written)\b", q.action + " " + q.completion_criteria, re.I))
        declared = explicit_test_count(writing)
        ordinals = [i for word, i in (("first", 1), ("second", 2), ("third", 3), ("fourth", 4), ("fifth", 5))
                    if re.search(rf"\b{word}\s+(?:unit\s+)?test\b", writing, re.I)]
        if (declared is not None and declared != requested_count) or (declared is None and max(ordinals, default=0) != requested_count):
            issues.add("duplicate_or_contradiction")
    seen_criteria = set()
    for index, quest in enumerate(plan.quests):
        normalized = " ".join(quest.completion_criteria.casefold().split())
        if normalized in seen_criteria:
            issues.add("unobservable_criteria")
        seen_criteria.add(normalized)
        if re.search(r"\b(?:research|search|summariz\w*)\b", quest.action, re.I) and not re.search(r"\b(?:slide|deck)\b", quest.action, re.I) and re.match(r"^(?:A |The )?Slides?\b", quest.completion_criteria, re.I):
            issues.add("sequencing_imperfection")
        text = " ".join([quest.title, quest.action, quest.completion_criteria, quest.hint or ""])
        external = list(positive_matches(EXTERNAL, text))
        if any(not optional_external_suggestion(text, match) for match in external):
            issues.add("external_dependency")
        if any(optional_external_suggestion(text, match) for match in external):
            issues.add("optional_tool_suggestion")
        if external and re.search(r"\b(?:no|without) (?:internet|downloads?|accounts?|shopping)|\boffline[- ]only\b", supplied, re.I):
            issues.add("explicit_constraint_violated")
        supplied_tools = supplied
        # FastAPI/Flask/Django are Python frameworks; naming their existing stack
        # already grounds Python, without licensing an invented framework/app.
        if re.search(r"\b(fastapi|flask|django)\b", supplied, re.I):
            supplied_tools += " Python"
        if any(not re.search(pattern, supplied_tools, re.I) and any(not optional_tool_example(text, match) for match in positive_matches(re.compile(pattern, re.I), text)) for pattern in TECHNOLOGIES):
            issues.add("unsupported_assumption")
        if re.search(r"\b(?:clean|tidy)\b.*\bdesk\b", supplied, re.I):
            for resource in (r"\bvacuum(?: cleaner)?\b", r"\bdisinfectant wipes?\b", r"\bmicrofiber cloths?\b", r"\bbucket of water\b", r"\blight source\b", r"\bnew chair\b"):
                if re.search(resource, quest.action, re.I) and not re.search(resource, supplied, re.I) and not re.search(r"\bif (?:already available|you already have|available)\b", quest.action, re.I):
                    issues.add("unsupported_assumption")
        if len(re.findall(r"\w+", quest.action)) < 2 or re.search(r"\b(work on it|make progress|do the task|do your best)\b", quest.action, re.I):
            issues.add("vague_action")
        if criteria_issue(quest.completion_criteria):
            issues.add("unobservable_criteria")
        if re.search(r"\bexisting\b.*\b(?:example )?lists\b", supplied, re.I) and re.search(r"\bcreate\b.*\b(?:new|local) list\b", quest.action, re.I):
            issues.add("unsupported_assumption")
        if re.search(r"\bexisting\b.*\bproject\b", supplied, re.I) and re.search(r"\binitialize\b.*\bproject\b", quest.action, re.I):
            issues.add("duplicate_or_contradiction")
        # An endpoint's actual response codes must come from user facts/local
        # inspection; an LLM cannot invent asserted API behavior.
        if "endpoint" in supplied.lower():
            codes = re.findall(r"\b([1-5]\d{2})\s+(?:OK|BAD REQUEST|UNAUTHORIZED|FORBIDDEN|NOT FOUND|status)\b", text, re.I)
            if any(not re.search(rf"\b{code}\b", supplied) for code in codes):
                issues.add("unsupported_assumption")
            if re.search(r"\bmock\w*\b.*\bendpoint\b.*\bpredefined response\b", quest.action, re.I):
                issues.add("unrelated")
        if quest.estimated_minutes > context.available_minutes and index == 0:
            issues.add("implausible_estimate")
        if index == 0 and context.energy == "low":
            if quest.estimated_minutes > min(context.available_minutes, 10):
                issues.add("implausible_estimate")
            if quest.difficulty == "hard":
                issues.add("inappropriate_difficulty")
        if quest.difficulty == "hard" and re.match(r"^(list|select|choose|open|read)\b", quest.action, re.I) and quest.estimated_minutes <= 10:
            issues.add("inappropriate_difficulty")
        if quest.estimated_minutes <= 10 and re.search(r"\b(build|implement|complete)\b.*\b(entire|full|complete)\b.*\b(app|application|project)\b", quest.action, re.I):
            issues.add("implausible_estimate")
    # Material, explicitly stated constraints stay hard failures.
    if re.search(r"\b(no[- ]cook|no (?:heat|stove|oven)|without (?:heat|cooking)|do not (?:cook|heat))\b", supplied, re.I):
        if any(any(positive_matches(HEAT, q.action)) for q in plan.quests):
            issues.add("explicit_constraint_violated")
    if re.search(r"\bvegetarian\b", supplied, re.I) and any(any(positive_matches(re.compile(r"\b(chicken|beef|pork|fish|tuna)\b", re.I), q.action)) for q in plan.quests):
        issues.add("explicit_constraint_violated")
    only = re.search(r"\b(?:using|with) only ([^;.]+)", supplied, re.I)
    if only:
        allowed = {ingredient_name(m.group(0)) for m in INGREDIENTS.finditer(only.group(1))}
        if allowed and any(ingredient_name(m.group(0)) not in allowed for q in plan.quests for m in positive_matches(INGREDIENTS, q.action)):
            issues.add("explicit_constraint_violated")
    for restriction, forbidden in (
        (r"\bno (?:login|auth\w*|accounts?)\b", r"\b(login|auth\w*|accounts?)\b"),
        (r"\bno (?:(?:login|auth\w*|accounts?) (?:or|and) )?(?:cloud )?deployment\b", r"\b(deploy\w*|hosting|cloud)\b"),
    ):
        if re.search(restriction, supplied, re.I) and any(any(positive_matches(re.compile(forbidden, re.I), q.action)) for q in plan.quests):
            issues.add("explicit_constraint_violated")
    if re.search(r"\bexisting\b.*\b(?:test runner|fixtures)\b", supplied, re.I) and any(re.search(r"\binstall\b.*\b(?:test runner|pytest)\b", q.action, re.I) for q in plan.quests):
        issues.add("explicit_constraint_violated")
    if re.search(r"\b(?:make|cook|prepare)\b.{0,100}\b(?:food|meal|eat|snack|sandwich|dish)\b", supplied, re.I):
        available = {ingredient_name(m.group(0)) for m in INGREDIENTS.finditer(supplied)}
        if available and any(ingredient_name(m.group(0)) not in available for q in plan.quests for m in positive_matches(INGREDIENTS, q.action)):
            issues.add("unsupported_assumption")
    # A named dish is a deliverable, not permission to substitute another meal.
    if re.search(r"\bsandwich\b", supplied, re.I) and not re.search(r"\bsandwich\b", combined, re.I):
        issues.add("unrelated")
    if any(any(positive_matches(re.compile(r"\b(?:taste|eat)\b.*\b(?:raw (?:flour|eggs?|meat|chicken)|uncooked (?:flour|eggs?|meat|chicken))\b", re.I), q.action)) for q in plan.quests):
        issues.add("unsafe_food_instruction")
    previous = {" ".join(q.action.casefold().split()) for q in grounding.completed}
    if any(" ".join(q.action.casefold().split()) in previous for q in plan.quests):
        issues.add("duplicate_or_contradiction")
    return tuple(sorted(issues))


def essential_checks(plan: QuestPlan, context: QuestlineContext,
                     grounding: GroundingContext) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Separate enforceable constraints from diagnostic-only quality warnings.

    Strict schema validation happens before this call and again at persistence.
    No model self-review or subjective warning can veto a conforming proposal.
    """
    findings = set(deterministic_issues(plan, context, grounding))
    warnings = findings & {"unobservable_criteria", "vague_action", "optional_tool_suggestion",
                           "sequencing_imperfection", "inappropriate_difficulty"}
    if "implausible_estimate" in findings:
        # Session capacity is explicit. Low-energy <=10 minute guidance and
        # effort opinions are advisory; obviously impossible whole-app estimates
        # remain blocking rather than treating them as a minor timing concern.
        impossible = any(q.estimated_minutes <= 10 and re.search(
            r"\b(build|implement|complete)\b.*\b(entire|full|complete)\b.*\b(app|application|project)\b",
            q.action, re.I) for q in plan.quests)
        if plan.quests[0].estimated_minutes <= context.available_minutes and not impossible:
            warnings.add("implausible_estimate")
    for quest in plan.quests:
        text = " ".join((quest.action, quest.completion_criteria, quest.hint or ""))
        if any(optional_tool_example(text, match) for pattern in TECHNOLOGIES
               for match in re.finditer(pattern, text, re.I)):
            warnings.add("optional_tool_suggestion")
    return tuple(sorted(findings - warnings)), tuple(sorted(warnings))


def reject_semantics(issues: tuple[str, ...] | list[str]) -> QuestError:
    return QuestError("AI_SEMANTIC_REJECTED", 502,
                      "The local model returned a plan that failed quality checks after one bounded correction. Your check-in is saved; retry generation.",
                      True, {"codes": sorted(set(issues)) or ["uncertain_relevance"]})


def classify_review(plan: QuestPlan, review: SemanticReview) -> tuple[tuple[str, ...], tuple[RepairTarget, ...]]:
    """Review is evidence to inspect, not authority over constraints or state."""
    if review.confidence != "high" or (not review.acceptable and not review.issues):
        return ("uncertain_review",), ()
    blocking = set(review.issues)
    blocking -= {"implausible_estimate", "inappropriate_difficulty"}
    for code in tuple(blocking):
        findings = [finding for finding in review.findings if finding.code == code]
        if code == "unsupported_assumption" and findings:
            optional_only = True
            for finding in findings:
                if finding.quest_index >= len(plan.quests):
                    optional_only = False; break
                text = str(getattr(plan.quests[finding.quest_index], finding.field))
                if finding.quote not in text or len(finding.quote) > 100:
                    optional_only = False; break
                matches = [match for pattern in TECHNOLOGIES for match in re.finditer(pattern, text, re.I)
                           if match.group(0).casefold() in finding.quote.casefold()]
                if not matches or not all(optional_tool_example(text, match) for match in matches):
                    optional_only = False; break
            if optional_only:
                blocking.remove(code)
    codes = tuple(sorted(blocking))
    if not codes:
        return (), ()
    if set(codes) <= REPAIRABLE_CODES and review.findings:
        fields, reasons = {}, {}
        for finding in review.findings:
            if finding.code not in codes:
                continue
            expected_field = "completion_criteria" if finding.code == "unobservable_criteria" else "action"
            if finding.quest_index >= len(plan.quests) or finding.field != expected_field or finding.quote not in getattr(plan.quests[finding.quest_index], finding.field):
                return codes, ()
            fields.setdefault(finding.quest_index, set()).add(expected_field)
            reasons.setdefault(finding.quest_index, set()).add(finding.code)
        if fields:
            return codes, tuple(RepairTarget(index, tuple(sorted(names)), tuple(sorted(reasons[index]))) for index, names in sorted(fields.items()))
    return codes, ()
