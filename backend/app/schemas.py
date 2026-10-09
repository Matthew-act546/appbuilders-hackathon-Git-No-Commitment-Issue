from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, ValidationInfo,
    field_validator, model_validator,
)
from pydantic_core import PydanticCustomError


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
    hint: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)] | None = None


class QuestPlan(StrictAIModel):
    quests: list[QuestProposal] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_plan(self, info: ValidationInfo) -> "QuestPlan":
        for field in ("title", "action"):
            values = [" ".join(getattr(quest, field).casefold().split()) for quest in self.quests]
            if len(set(values)) != len(values):
                raise PydanticCustomError("duplicate_quest_content", "Quest titles and actions must be distinct.")
        if info.context and self.quests[0].estimated_minutes > info.context["available_minutes"]:
            raise PydanticCustomError("first_quest_exceeds_capacity", "First quest estimate exceeds session capacity.")
        return self
