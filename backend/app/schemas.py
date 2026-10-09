from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo,
    TypeAdapter, UUID4, field_validator, model_validator,
)
from pydantic_core import PydanticCustomError

from .encouragement import safe_encouragement


class AIStatus(BaseModel):
    available: bool
    server_available: bool
    model_available: bool
    model: str
    message: str


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)

    @field_validator("prompt")
    @classmethod
    def trim_prompt(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Prompt must not be blank.")
        return value


class GenerateResponse(BaseModel):
    model: str
    response: str


# AI proposals are untrusted content, separate from future public/state schemas.
class StrictAIModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class CheckInInput(StrictAIModel):
    goal: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    available_minutes: int = Field(ge=1, le=1440)
    energy: Literal["low", "medium", "high"]
    deadline: AwareDatetime | None = None

    @field_validator("deadline", mode="before")
    @classmethod
    def parse_deadline(cls, value):
        # FastAPI validates decoded JSON dictionaries; permit only timestamp strings,
        # aware datetimes or null, never numeric Unix timestamps/coercions.
        return TypeAdapter(AwareDatetime).validate_python(value) if isinstance(value, str) else value

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value: datetime | None) -> datetime | None:
        return value.astimezone(timezone.utc) if value is not None else None


class QuestProposal(StrictAIModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    action: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    completion_criteria: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    estimated_minutes: int = Field(ge=1, le=1440)
    difficulty: Literal["easy", "medium", "hard"]
    completion_encouragement: str | None = Field(default=None, max_length=500, description="Optional short completion-only message; invalid copy is discarded.")
    hint: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None

    @field_validator("completion_encouragement", mode="before")
    @classmethod
    def optional_encouragement(cls, value, info: ValidationInfo):
        return safe_encouragement(value, info.data.get("title", ""), action=info.data.get("action", ""))


class QuestPlan(StrictAIModel):
    quests: list[QuestProposal] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def validate_plan(self, info: ValidationInfo) -> "QuestPlan":
        for field in ("title", "action"):
            values = [" ".join(getattr(quest, field).casefold().split()) for quest in self.quests]
            if len(set(values)) != len(values):
                raise PydanticCustomError("duplicate_quest_content", "Quest titles and actions must be distinct.")
        if info.context and self.quests[0].estimated_minutes > info.context["available_minutes"]:
            raise PydanticCustomError("first_quest_exceeds_capacity", "First quest estimate exceeds session capacity.")
        if info.context and len(self.quests) > info.context.get("max_quests", 6):
            raise PydanticCustomError("campaign_stage_limit", "Replacement exceeds the remaining campaign stage slots.")
        if info.context and len(self.quests) < info.context.get("min_quests", 1):
            raise PydanticCustomError("campaign_stage_minimum", "The updated campaign needs at least two total stages.")
        return self


# Trusted-state inputs and public projections are separate from AI proposals.
class QuestlineContext(CheckInInput):
    contextual_notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


class ReplacementPlan(QuestPlan):
    quests: list[QuestProposal] = Field(min_length=1, max_length=6)


class PlanMetadata(StrictAIModel):
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    model_tag: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    prompt_version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] | None = None
    change_reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None


class RevisionRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    expected_revision: int = Field(ge=1)


class ProfileView(BaseModel):
    id: Literal[1]
    total_xp: int = Field(ge=0)
    level: int = Field(ge=1)


class ProgressView(BaseModel):
    completed_count: int = Field(ge=0)
    remaining_count: int = Field(ge=0)
    total_count: int = Field(ge=1)


class QuestView(BaseModel):
    id: str
    order: int
    plan_version: int
    status: Literal["active", "paused", "completed"]
    title: str
    action: str
    completion_criteria: str
    estimated_minutes: int
    difficulty: Literal["easy", "medium", "hard"]
    xp_reward: Literal[10, 20, 30]
    hint: str | None
    starting_action: str | None
    completed_at: AwareDatetime | None
    completion_encouragement: str | None = None


class QuestlineSummary(BaseModel):
    id: str
    goal: str
    status: Literal["active", "paused", "completed"]
    deadline: AwareDatetime | None
    plan_version: int
    revision: int
    progress: ProgressView
    created_at: AwareDatetime
    updated_at: AwareDatetime


class QuestlineView(QuestlineSummary):
    available_minutes: int
    energy: Literal["low", "medium", "high"]
    current_quest: QuestView | None
    completed_quests: list[QuestView]


class QuestlineList(BaseModel):
    items: list[QuestlineSummary]
    limit: int
    offset: int
    has_more: bool


class CompletionView(BaseModel):
    outcome: Literal["completed", "already_completed"]
    awarded_xp: Literal[0, 10, 20, 30]
    profile: ProfileView
    questline: QuestlineView


class ErrorInfo(BaseModel):
    code: str
    message: str
    retryable: bool
    request_id: str
    details: dict | None = None


class ErrorView(BaseModel):
    error: ErrorInfo


class CheckInStart(QuestlineContext):
    mode: Literal["start"]


class CheckInAnswer(RevisionRequest):
    mode: Literal["answer"]
    check_in_id: Annotated[UUID4, Field(strict=False)]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class GenerateQuestlineRequest(StrictAIModel):
    check_in_id: Annotated[UUID4, Field(strict=False)]
    expected_check_in_revision: int = Field(ge=1)


class ReplanRequest(RevisionRequest):
    available_minutes: int = Field(ge=1, le=1440)
    energy: Literal["low", "medium", "high"]
    deadline: AwareDatetime | None = None
    contextual_notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    _parse_deadline = field_validator("deadline", mode="before")(CheckInInput.parse_deadline.__func__)
    _normalize_deadline = field_validator("deadline")(CheckInInput.normalize_deadline.__func__)


class CheckInView(BaseModel):
    id: str
    status: Literal["needs_follow_up", "ready", "consumed"]
    revision: int
    context: QuestlineContext
    question: str | None
    summary: str | None
    questline_id: str | None
    clarification_answer: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CompletedMilestone(StrictAIModel):
    title: str
    action: str
    completion_criteria: str


class GroundingContext(StrictAIModel):
    summary: Annotated[str, StringConstraints(min_length=1, max_length=2000)]
    clarification_answer: str | None = None
    contextual_notes: str | None = None
    change_reason: str | None = None
    completed: list[CompletedMilestone] = Field(default_factory=list)


SemanticCode = Literal["unsupported_assumption", "unrelated", "vague_action", "unobservable_criteria",
                       "implausible_estimate", "external_dependency", "duplicate_or_contradiction", "inappropriate_difficulty"]


class SemanticFinding(StrictAIModel):
    quest_index: int = Field(ge=0, le=5)
    field: Literal["title", "action", "completion_criteria", "hint", "estimated_minutes", "difficulty"]
    code: SemanticCode
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class SemanticReview(StrictAIModel):
    acceptable: bool
    confidence: Literal["high", "low"]
    issues: list[SemanticCode] = Field(max_length=8)
    findings: list[SemanticFinding] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def consistent_decision(self):
        if any(f.code not in self.issues for f in self.findings):
            raise ValueError("Findings must correspond to declared issues.")
        if self.acceptable and (self.confidence != "high" or self.issues or self.findings):
            raise ValueError("Acceptance requires high confidence and no issues.")
        return self


class QuestContentRepair(StrictAIModel):
    """Untrusted local patch, never identifiers, rewards, status or plan structure."""
    quest_index: int = Field(ge=0, le=5)
    action: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] | None = None
    completion_criteria: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None


class QuestPlanRepair(StrictAIModel):
    repairs: list[QuestContentRepair] = Field(min_length=1, max_length=6)
