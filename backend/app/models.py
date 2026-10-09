"""Internal SQLite state. Public DTOs deliberately expose only current/history."""
from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def integer_check(name: str, minimum: int = 1, maximum: int | None = None) -> CheckConstraint:
    return CheckConstraint(f"typeof({name})='integer' AND {name}>={minimum}" +
                           (f" AND {name}<={maximum}" if maximum is not None else ""))


def text_check(name: str, maximum: int, *, nullable: bool = False, minimum: int = 1) -> CheckConstraint:
    expression = f"length(trim({name}))>={minimum} AND length({name})<={maximum}"
    return CheckConstraint(f"{name} IS NULL OR ({expression})" if nullable else expression)


class Timestamps:
    created_at: Mapped[str]
    updated_at: Mapped[str]


class Profile(Timestamps, Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    total_xp: Mapped[int] = mapped_column(default=0)
    __table_args__ = (CheckConstraint("id=1"), integer_check("total_xp", 0))
    questlines: Mapped[list["Questline"]] = relationship(back_populates="profile", viewonly=True)


class Questline(Timestamps, Base):
    __tablename__ = "questlines"
    id: Mapped[str] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    goal: Mapped[str]
    check_in_summary: Mapped[str]
    available_minutes: Mapped[int]
    energy: Mapped[str]
    deadline: Mapped[str | None]
    contextual_notes: Mapped[str | None]
    status: Mapped[str]
    plan_version: Mapped[int]
    revision: Mapped[int]
    active_quest_id: Mapped[str | None]
    completed_at: Mapped[str | None]
    __table_args__ = (
        ForeignKeyConstraint(["active_quest_id", "id"], ["quests.id", "quests.questline_id"], deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["id", "plan_version"], ["plan_versions.questline_id", "plan_versions.version"], deferrable=True, initially="DEFERRED"),
        text_check("goal", 4000), text_check("check_in_summary", 2000),
        text_check("contextual_notes", 2000, nullable=True, minimum=0),
        integer_check("available_minutes", 1, 1440), integer_check("plan_version"), integer_check("revision"),
        CheckConstraint("energy IN ('low','medium','high')"),
        CheckConstraint("status IN ('active','paused','completed')"),
        CheckConstraint("(status IN ('active','paused') AND active_quest_id IS NOT NULL AND completed_at IS NULL) OR "
                        "(status='completed' AND active_quest_id IS NULL AND completed_at IS NOT NULL)"),
        Index("ix_questlines_saved", "profile_id", "updated_at", "id"),
        Index("ix_questlines_status", "profile_id", "status"),
    )
    profile: Mapped[Profile] = relationship(back_populates="questlines", viewonly=True)
    quests: Mapped[list["Quest"]] = relationship(primaryjoin="Questline.id == Quest.questline_id",
                                                foreign_keys="Quest.questline_id", viewonly=True)
    versions: Mapped[list["PlanVersion"]] = relationship(primaryjoin="Questline.id == PlanVersion.questline_id",
                                                        foreign_keys="PlanVersion.questline_id", viewonly=True)


class PlanVersion(Base):
    __tablename__ = "plan_versions"
    questline_id: Mapped[str] = mapped_column(ForeignKey("questlines.id"), primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    reason: Mapped[str]
    available_minutes: Mapped[int]
    energy: Mapped[str]
    deadline: Mapped[str | None]
    contextual_notes: Mapped[str | None]
    change_reason: Mapped[str | None]
    check_in_summary: Mapped[str]
    generated_quest_count: Mapped[int]
    model_tag: Mapped[str | None]
    prompt_version: Mapped[str | None]
    created_at: Mapped[str]
    __table_args__ = (
        integer_check("version"), integer_check("available_minutes", 1, 1440), integer_check("generated_quest_count", 1, 6),
        CheckConstraint("energy IN ('low','medium','high')"),
        CheckConstraint("(reason='initial' AND version=1 AND generated_quest_count>=2) OR (reason='replan' AND version>1)"),
        text_check("check_in_summary", 2000), text_check("contextual_notes", 2000, nullable=True, minimum=0),
        text_check("change_reason", 1000, nullable=True, minimum=0),
        text_check("model_tag", 200, nullable=True), text_check("prompt_version", 200, nullable=True),
    )


class Quest(Timestamps, Base):
    __tablename__ = "quests"
    id: Mapped[str] = mapped_column(primary_key=True)
    questline_id: Mapped[str] = mapped_column(ForeignKey("questlines.id"))
    plan_version: Mapped[int]
    position: Mapped[int]
    title: Mapped[str]
    action: Mapped[str]
    completion_criteria: Mapped[str]
    estimated_minutes: Mapped[int]
    difficulty: Mapped[str]
    xp_reward: Mapped[int]
    status: Mapped[str]
    hint: Mapped[str | None]
    starting_action: Mapped[str | None]
    completed_at: Mapped[str | None]
    superseded_at: Mapped[str | None]
    completion_encouragement: Mapped[str | None] = mapped_column(sort_order=1000)
    __table_args__ = (
        ForeignKeyConstraint(["questline_id", "plan_version"], ["plan_versions.questline_id", "plan_versions.version"]),
        UniqueConstraint("questline_id", "plan_version", "position"), UniqueConstraint("id", "questline_id"),
        UniqueConstraint("id", "xp_reward"),
        integer_check("plan_version"), integer_check("position"), integer_check("estimated_minutes", 1, 1440),
        integer_check("xp_reward", 10, 30),
        text_check("title", 100), text_check("action", 2000), text_check("completion_criteria", 1000),
        text_check("hint", 1000, nullable=True), text_check("starting_action", 1000, nullable=True),
        CheckConstraint("(difficulty='easy' AND xp_reward=10) OR (difficulty='medium' AND xp_reward=20) OR (difficulty='hard' AND xp_reward=30)"),
        CheckConstraint("status IN ('locked','active','paused','completed','superseded')"),
        CheckConstraint("(status='completed' AND completed_at IS NOT NULL AND superseded_at IS NULL) OR "
                        "(status='superseded' AND superseded_at IS NOT NULL AND completed_at IS NULL) OR "
                        "(status IN ('locked','active','paused') AND completed_at IS NULL AND superseded_at IS NULL)"),
        Index("uq_quest_current", "questline_id", unique=True, sqlite_where=text("status IN ('active','paused')")),
        Index("ix_quest_plan_order", "questline_id", "plan_version", "status", "position"),
    )
    completion: Mapped["Completion | None"] = relationship(viewonly=True)


class Completion(Base):
    __tablename__ = "completions"
    quest_id: Mapped[str] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    xp_awarded: Mapped[int]
    completed_at: Mapped[str]
    __table_args__ = (
        ForeignKeyConstraint(["quest_id", "xp_awarded"], ["quests.id", "quests.xp_reward"]),
        CheckConstraint("typeof(xp_awarded)='integer' AND xp_awarded IN (10,20,30)"),
        Index("ix_completion_history", "profile_id", "completed_at"),
    )


class TransitionReceipt(Base):
    """Only synchronous pause/resume replay protection; no AI leases in Phase 2."""
    __tablename__ = "transition_receipts"
    key: Mapped[str] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    questline_id: Mapped[str] = mapped_column(ForeignKey("questlines.id"))
    action: Mapped[str]
    expected_revision: Mapped[int]
    created_at: Mapped[str]
    __table_args__ = (CheckConstraint("action IN ('pause','resume')"), integer_check("expected_revision"))


class CheckIn(Timestamps, Base):
    __tablename__ = "check_ins"
    id: Mapped[str] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    goal: Mapped[str]
    available_minutes: Mapped[int]
    energy: Mapped[str]
    deadline: Mapped[str | None]
    contextual_notes: Mapped[str | None]
    status: Mapped[str]
    revision: Mapped[int]
    summary: Mapped[str | None]
    follow_up_question: Mapped[str | None]
    follow_up_answer: Mapped[str | None]
    follow_up_count: Mapped[int]
    questline_id: Mapped[str | None] = mapped_column(ForeignKey("questlines.id"), unique=True)
    __table_args__ = (
        text_check("goal", 4000), integer_check("available_minutes", 1, 1440), integer_check("revision"),
        CheckConstraint("energy IN ('low','medium','high')"),
        text_check("contextual_notes", 2000, nullable=True, minimum=0), text_check("summary", 2000, nullable=True),
        text_check("follow_up_question", 300, nullable=True), text_check("follow_up_answer", 2000, nullable=True),
        CheckConstraint("typeof(follow_up_count)='integer' AND follow_up_count IN (0,1)"),
        CheckConstraint("(follow_up_count=0 AND follow_up_question IS NULL AND follow_up_answer IS NULL) OR "
                        "(follow_up_count=1 AND follow_up_question IS NOT NULL)"),
        CheckConstraint("(status='needs_follow_up' AND follow_up_count=1 AND follow_up_answer IS NULL AND summary IS NULL AND questline_id IS NULL) OR "
                        "(status='ready' AND summary IS NOT NULL AND questline_id IS NULL AND (follow_up_count=0 OR follow_up_answer IS NOT NULL)) OR "
                        "(status='consumed' AND summary IS NOT NULL AND questline_id IS NOT NULL AND (follow_up_count=0 OR follow_up_answer IS NOT NULL))"),
        Index("ix_check_in_saved", "profile_id", "updated_at", "id"),
    )


class GenerationIntent(Timestamps, Base):
    """Local intent reservation, bounded lease and atomic result identifier."""
    __tablename__ = "generation_intents"
    key: Mapped[str] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"))
    operation: Mapped[str]
    target_id: Mapped[str]
    request_hash: Mapped[str]
    state: Mapped[str]
    attempt_number: Mapped[int]
    lease_expires_at: Mapped[str | None]
    resource_id: Mapped[str | None]
    error_code: Mapped[str | None]
    __table_args__ = (
        CheckConstraint("operation IN ('check_in_start','check_in_answer','generate','replan')"),
        CheckConstraint("state IN ('pending','succeeded','failed')"), integer_check("attempt_number"),
        CheckConstraint("length(request_hash)=64"),
        CheckConstraint("(state='pending' AND lease_expires_at IS NOT NULL AND resource_id IS NULL) OR "
                        "(state='succeeded' AND lease_expires_at IS NULL AND resource_id IS NOT NULL) OR "
                        "(state='failed' AND lease_expires_at IS NULL AND resource_id IS NULL)"),
        Index("uq_pending_generation_target", "operation", "target_id", unique=True, sqlite_where=text("state='pending'")),
        Index("ix_intent_recovery", "state", "lease_expires_at"),
    )
