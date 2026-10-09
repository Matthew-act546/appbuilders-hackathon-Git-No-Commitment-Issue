from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from ..database import unit_of_work
from ..errors import QuestError
from ..models import Completion, PlanVersion, Profile, Quest, Questline, TransitionReceipt
from ..schemas import (
    CompletionView, PlanMetadata, ProfileView, ProgressView, QuestlineContext,
    QuestlineList, QuestlineSummary, QuestlineView, QuestPlan, QuestView,
    ReplacementPlan, RevisionRequest,
)

XP_BY_DIFFICULTY = {"easy": 10, "medium": 20, "hard": 30}


def utc_text(value: datetime | None = None) -> str:
    value = value or datetime.now(timezone.utc)
    if value.utcoffset() is None:
        raise ValueError("Timestamps require a timezone.")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def valid_id(value: str) -> str:
    try:
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError
        return str(parsed)
    except (ValueError, TypeError, AttributeError):
        raise QuestError("VALIDATION_ERROR", 422, "A UUIDv4 identifier is required.") from None


def require_integrity(condition: bool) -> None:
    if not condition:
        raise QuestError("STORAGE_UNAVAILABLE", 503, "Stored quest state is inconsistent. Restore a verified backup.")


def profile_view(session: Session) -> ProfileView:
    profile = session.get(Profile, 1)
    require_integrity(profile is not None)
    return ProfileView(id=1, total_xp=profile.total_xp, level=profile.total_xp // 100 + 1)


def line_quests(session: Session, line: Questline) -> list[Quest]:
    return list(session.scalars(select(Quest).where(Quest.questline_id == line.id)))


def verify_line(session: Session, line: Questline) -> None:
    quests = line_quests(session, line)
    current = [q for q in quests if q.status in ("active", "paused")]
    remaining = [q for q in quests if q.status in ("active", "paused", "locked")]
    require_integrity(all(q.plan_version == line.plan_version for q in remaining))
    if line.status == "completed":
        require_integrity(not remaining and line.active_quest_id is None and line.completed_at is not None)
    else:
        require_integrity(len(current) == 1 and current[0].id == line.active_quest_id and current[0].status == line.status)
        require_integrity(line.completed_at is None and current[0].position == min(q.position for q in remaining))
    versions = list(session.scalars(select(PlanVersion).where(PlanVersion.questline_id == line.id)))
    require_integrity(sorted(v.version for v in versions) == list(range(1, line.plan_version + 1)))
    for version in versions:
        group = [q for q in quests if q.plan_version == version.version]
        require_integrity(len(group) == version.generated_quest_count)
        require_integrity(all(q.status in ("completed", "superseded") for q in group) if version.version < line.plan_version else True)
    records = {r.quest_id: r for r in session.scalars(select(Completion).join(Quest, Completion.quest_id == Quest.id)
                                                    .where(Quest.questline_id == line.id))}
    require_integrity(set(records) == {q.id for q in quests if q.status == "completed"})
    for quest in quests:
        require_integrity(quest.xp_reward == XP_BY_DIFFICULTY.get(quest.difficulty))
        if quest.id in records:
            record = records[quest.id]
            require_integrity(record.profile_id == line.profile_id and record.xp_awarded == quest.xp_reward and
                              record.completed_at == quest.completed_at)


def verify_database(session: Session) -> None:
    require_integrity(list(session.scalars(select(Profile.id))) == [1])
    for line in session.scalars(select(Questline)):
        verify_line(session, line)
    total = session.scalar(select(func.coalesce(func.sum(Completion.xp_awarded), 0)))
    require_integrity(profile_view(session).total_xp == total)


def quest_view(quest: Quest) -> QuestView:
    # Deliberate field list; never serialize ORM relationships or hidden states.
    return QuestView(id=quest.id, order=quest.position, plan_version=quest.plan_version, status=quest.status,
                     title=quest.title, action=quest.action, completion_criteria=quest.completion_criteria,
                     estimated_minutes=quest.estimated_minutes, difficulty=quest.difficulty, xp_reward=quest.xp_reward,
                     hint=quest.hint, starting_action=quest.starting_action, completed_at=quest.completed_at)


def summary_view(session: Session, line: Questline) -> QuestlineSummary:
    completed = session.scalar(select(func.count()).select_from(Quest).where(Quest.questline_id == line.id, Quest.status == "completed"))
    remaining = session.scalar(select(func.count()).select_from(Quest).where(Quest.questline_id == line.id,
                               Quest.plan_version == line.plan_version, Quest.status.in_(("active", "paused", "locked"))))
    return QuestlineSummary(id=line.id, goal=line.goal, status=line.status, deadline=line.deadline,
                            plan_version=line.plan_version, revision=line.revision,
                            progress=ProgressView(completed_count=completed, remaining_count=remaining, total_count=completed + remaining),
                            created_at=line.created_at, updated_at=line.updated_at)


def public_view(session: Session, line: Questline) -> QuestlineView:
    current = session.get(Quest, line.active_quest_id) if line.active_quest_id else None
    if current:
        require_integrity(current.status in ("active", "paused") and current.questline_id == line.id)
    history = session.scalars(select(Quest).where(Quest.questline_id == line.id, Quest.status == "completed")
                              .order_by(Quest.completed_at, Quest.position, Quest.id))
    return QuestlineView(**summary_view(session, line).model_dump(), available_minutes=line.available_minutes,
                         energy=line.energy, current_quest=quest_view(current) if current else None,
                         completed_quests=[quest_view(quest) for quest in history])


def get_line(session: Session, line_id: str) -> Questline:
    line = session.get(Questline, line_id)
    if line is None:
        raise QuestError("QUESTLINE_NOT_FOUND", 404, "Questline not found.")
    return line


def check_revision(line: Questline, revision: int) -> None:
    if line.revision != revision:
        raise QuestError("STALE_REVISION", 409, "The questline changed. Reload and try again.", True,
                         {"current_revision": line.revision})


def context_values(context: QuestlineContext) -> dict:
    return {"available_minutes": context.available_minutes, "energy": context.energy,
            "deadline": utc_text(context.deadline) if context.deadline else None, "contextual_notes": context.contextual_notes}


def add_version(session: Session, line: Questline, plan: QuestPlan, metadata: PlanMetadata, now: str,
                *, initial: bool, completed_count: int = 0) -> str:
    version = PlanVersion(questline_id=line.id, version=line.plan_version, reason="initial" if initial else "replan",
                          available_minutes=line.available_minutes, energy=line.energy, deadline=line.deadline,
                          contextual_notes=line.contextual_notes, change_reason=metadata.change_reason,
                          check_in_summary=metadata.summary, generated_quest_count=len(plan.quests),
                          model_tag=metadata.model_tag, prompt_version=metadata.prompt_version, created_at=now)
    session.add(version)
    session.flush()  # FK parent before quests; current pointer is deferred until commit.
    ids = [str(uuid4()) for _ in plan.quests]
    for index, (proposal, quest_id) in enumerate(zip(plan.quests, ids)):
        session.add(Quest(id=quest_id, questline_id=line.id, plan_version=line.plan_version,
                          position=completed_count + index + 1, title=proposal.title, action=proposal.action,
                          completion_criteria=proposal.completion_criteria, estimated_minutes=proposal.estimated_minutes,
                          difficulty=proposal.difficulty, xp_reward=XP_BY_DIFFICULTY[proposal.difficulty],
                          status="active" if index == 0 else "locked", hint=proposal.hint, starting_action=None,
                          created_at=now, updated_at=now, completed_at=None, superseded_at=None))
    session.flush()
    return ids[0]


class QuestService:
    def __init__(self, database: Engine):
        self.database = database

    def create_questline(self, context: QuestlineContext, plan: QuestPlan, *, summary: str,
                         model_tag: str | None = None, prompt_version: str | None = None) -> QuestlineView:
        # Revalidate even a mutated/model_construct proposal; never trust instance identity.
        context = QuestlineContext.model_validate(context.model_dump())
        plan = QuestPlan.model_validate(plan.model_dump(), context={"available_minutes": context.available_minutes})
        metadata = PlanMetadata(summary=summary, model_tag=model_tag, prompt_version=prompt_version)
        now = utc_text()
        with unit_of_work(self.database, write=True) as session:
            line = Questline(id=str(uuid4()), profile_id=1, goal=context.goal, check_in_summary=metadata.summary,
                             **context_values(context), status="active", plan_version=1, revision=1,
                             active_quest_id=str(uuid4()), created_at=now, updated_at=now, completed_at=None)
            session.add(line)
            session.flush()
            line.active_quest_id = add_version(session, line, plan, metadata, now, initial=True)
            session.flush()
            verify_database(session)
            result = public_view(session, line)
        return result

    def get_questline(self, line_id: str) -> QuestlineView:
        with unit_of_work(self.database) as session:
            line = get_line(session, valid_id(line_id))
            verify_line(session, line)
            return public_view(session, line)

    def list_questlines(self, *, limit: int = 20, offset: int = 0,
                       status: Literal["active", "paused", "completed"] | None = None) -> QuestlineList:
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0 or status not in (None, "active", "paused", "completed"):
            raise QuestError("VALIDATION_ERROR", 422, "Invalid saved-questline query.")
        with unit_of_work(self.database) as session:
            query = select(Questline).where(Questline.profile_id == 1)
            if status:
                query = query.where(Questline.status == status)
            lines = list(session.scalars(query.order_by(Questline.updated_at.desc(), Questline.id).limit(limit + 1).offset(offset)))
            return QuestlineList(items=[summary_view(session, line) for line in lines[:limit]], limit=limit,
                                 offset=offset, has_more=len(lines) > limit)

    def get_profile(self) -> ProfileView:
        with unit_of_work(self.database) as session:
            return profile_view(session)

    def complete_quest(self, quest_id: str, expected_revision: int) -> CompletionView:
        revision = RevisionRequest(expected_revision=expected_revision).expected_revision
        with unit_of_work(self.database, write=True) as session:
            quest = session.get(Quest, valid_id(quest_id))
            if quest is None or quest.status in ("locked", "superseded"):
                raise QuestError("QUEST_NOT_FOUND", 404, "Quest not found.")
            line = get_line(session, quest.questline_id)
            verify_line(session, line)
            record = session.get(Completion, quest.id)
            if record:
                return CompletionView(outcome="already_completed", awarded_xp=0,
                                      profile=profile_view(session), questline=public_view(session, line))
            if line.status == "paused":
                raise QuestError("QUESTLINE_PAUSED", 409, "Resume this questline before completing a quest.")
            if line.status != "active" or quest.status != "active" or line.active_quest_id != quest.id:
                raise QuestError("INVALID_STATE", 409, "Only the current active quest can be completed.")
            check_revision(line, revision)
            now = utc_text()
            quest.status, quest.completed_at, quest.updated_at = "completed", now, now
            session.add(Completion(quest_id=quest.id, profile_id=1, xp_awarded=quest.xp_reward, completed_at=now))
            profile = session.get(Profile, 1)
            profile.total_xp += quest.xp_reward
            profile.updated_at = now
            session.flush()  # Release unique current slot before unlocking the next.
            next_quest = session.scalar(select(Quest).where(Quest.questline_id == line.id, Quest.plan_version == line.plan_version,
                                                          Quest.status == "locked").order_by(Quest.position).limit(1))
            if next_quest:
                next_quest.status, next_quest.updated_at = "active", now
                line.active_quest_id = next_quest.id
            else:
                line.status, line.active_quest_id, line.completed_at = "completed", None, now
            line.revision += 1
            line.updated_at = now
            session.flush()
            verify_database(session)
            result = CompletionView(outcome="completed", awarded_xp=quest.xp_reward,
                                    profile=profile_view(session), questline=public_view(session, line))
        return result

    def set_paused(self, line_id: str, expected_revision: int, *, paused: bool, idempotency_key: str) -> QuestlineView:
        line_id, key = valid_id(line_id), valid_id(idempotency_key)
        revision = RevisionRequest(expected_revision=expected_revision).expected_revision
        if type(paused) is not bool:
            raise QuestError("VALIDATION_ERROR", 422, "A pause/resume operation is required.")
        action, desired = ("pause", "paused") if paused else ("resume", "active")
        with unit_of_work(self.database, write=True) as session:
            line = get_line(session, line_id)
            receipt = session.get(TransitionReceipt, key)
            if receipt:
                if (receipt.questline_id, receipt.action, receipt.expected_revision) != (line_id, action, revision):
                    raise QuestError("IDEMPOTENCY_CONFLICT", 409, "This idempotency key belongs to a different request.")
                return public_view(session, line)  # Never replay an old pause after resume.
            if line.status == "completed":
                raise QuestError("INVALID_STATE", 409, "A completed questline cannot be paused or resumed.")
            verify_line(session, line)
            if line.status != desired:
                check_revision(line, revision)
                now = utc_text()
                quest = session.get(Quest, line.active_quest_id)
                quest.status, quest.updated_at = desired, now
                line.status, line.updated_at = desired, now
                line.revision += 1
            session.add(TransitionReceipt(key=key, profile_id=1, questline_id=line.id, action=action,
                                          expected_revision=revision, created_at=utc_text()))
            session.flush()
            verify_database(session)
            result = public_view(session, line)
        return result

    def replace_unfinished(self, line_id: str, expected_revision: int, plan: ReplacementPlan,
                           context: QuestlineContext, *, summary: str, reason: str | None = None,
                           model_tag: str | None = None, prompt_version: str | None = None) -> QuestlineView:
        revision = RevisionRequest(expected_revision=expected_revision).expected_revision
        context = QuestlineContext.model_validate(context.model_dump())
        plan = ReplacementPlan.model_validate(plan.model_dump(), context={"available_minutes": context.available_minutes})
        metadata = PlanMetadata(summary=summary, change_reason=reason, model_tag=model_tag, prompt_version=prompt_version)
        with unit_of_work(self.database, write=True) as session:
            line = get_line(session, valid_id(line_id))
            verify_line(session, line)
            if line.status != "active":
                raise QuestError("QUESTLINE_PAUSED" if line.status == "paused" else "INVALID_STATE", 409,
                                 "Only active unfinished questlines can be replanned.")
            check_revision(line, revision)
            if line.goal != context.goal:
                raise QuestError("VALIDATION_ERROR", 422, "Replanning cannot change the goal.")
            quests = line_quests(session, line)
            completed = [q for q in quests if q.status == "completed"]
            completed_actions = {" ".join(q.action.casefold().split()) for q in completed}
            if any(" ".join(q.action.casefold().split()) in completed_actions for q in plan.quests):
                raise QuestError("VALIDATION_ERROR", 422, "Replacement work repeats a completed action.")
            now = utc_text()
            for quest in quests:
                if quest.status in ("active", "locked"):
                    quest.status, quest.superseded_at, quest.updated_at = "superseded", now, now
            session.flush()  # Vacate current slot before replacement insertion.
            line.plan_version += 1
            line.revision += 1
            line.updated_at = now
            line.check_in_summary = metadata.summary
            for key, value in context_values(context).items():
                setattr(line, key, value)
            line.active_quest_id = add_version(session, line, plan, metadata, now, initial=False, completed_count=len(completed))
            session.flush()
            verify_database(session)
            result = public_view(session, line)
        return result
