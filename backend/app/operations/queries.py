import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import Date, and_, case, cast, func, or_, select, true
from sqlalchemy.orm import aliased

from app.core.security import now
from app.models import (
    AnalysisItem,
    AnalysisRun,
    AnalysisTemplate,
    Document,
    Membership,
    ReviewEvent,
    SourceRevision,
    User,
)


class Filters(BaseModel):
    scope: Literal["current", "superseded", "all"] = "current"
    engine: Literal["deterministic", "mock", "openai", "all"] = "deterministic"
    kind: Literal["field", "risk", "obligation", "review"] | None = None
    document_id: uuid.UUID | None = None
    review_status: Literal["pending", "corrected", "approved", "rejected"] | None = None
    obligation_status: Literal["open", "in_progress", "completed", "dismissed"] | None = None
    severity: Literal["low", "medium", "high"] | None = None
    party: str = Field(default="", max_length=100)
    assignee_id: uuid.UUID | None = None
    unassigned: bool = False
    deadline_from: date | None = None
    deadline_to: date | None = None
    timing: Literal["overdue", "upcoming", "unknown"] | None = None
    assignment_timing: Literal["overdue", "upcoming", "unknown"] | None = None
    work_status: Literal["open", "done"] | None = None
    unresolved: bool = False
    focus: (
        Literal[
            "records",
            "risks",
            "obligations",
            "pending_reviews",
            "open_obligations",
            "overdue_obligations",
            "upcoming_obligations",
            "open_assignments",
            "unresolved",
        ]
        | None
    ) = None
    as_of: date = Field(default_factory=lambda: now().date())

    @model_validator(mode="after")
    def valid_ranges(self):
        if self.deadline_from and self.deadline_to and self.deadline_from > self.deadline_to:
            raise ValueError("Deadline start must not follow end")
        if self.unassigned and self.assignee_id:
            raise ValueError("Choose an assignee or unassigned, not both")
        return self


def portfolio(org):
    """Shared SQL projection. Template families remain separate business records."""
    family = (
        select(AnalysisTemplate.id, AnalysisTemplate.id.label("family_id"))
        .where(
            AnalysisTemplate.organization_id == org,
            AnalysisTemplate.parent_id.is_(None),
        )
        .cte("template_family", recursive=True)
    )
    child = aliased(AnalysisTemplate)
    family = family.union_all(
        select(child.id, family.c.family_id)
        .join(
            family,
            child.parent_id == family.c.id,
        )
        .where(child.organization_id == org)
    )
    ranked = (
        select(
            AnalysisRun.id.label("run_id"),
            func.row_number()
            .over(
                partition_by=[AnalysisRun.left_revision_id, family.c.family_id, AnalysisRun.engine],
                order_by=[AnalysisRun.created_at.desc(), AnalysisRun.id.desc()],
            )
            .label("rank"),
            family.c.family_id,
        )
        .join(family, family.c.id == AnalysisRun.template_id)
        .where(
            AnalysisRun.organization_id == org,
            AnalysisRun.state == "completed",
            AnalysisRun.mode == "extract",
        )
        .cte("ranked_runs")
    )
    member, person = aliased(Membership), aliased(User)
    completion = (
        select(func.max(ReviewEvent.created_at))
        .where(
            ReviewEvent.item_id == AnalysisItem.id,
            or_(
                and_(AnalysisItem.kind == "obligation", ReviewEvent.action == "obligation"),
                and_(
                    AnalysisItem.kind != "obligation", ReviewEvent.action.in_(["approve", "reject"])
                ),
            ),
        )
        .correlate(AnalysisItem)
        .scalar_subquery()
    )
    raw_deadline = AnalysisItem.original["deadline"].astext
    deadline = case(
        (raw_deadline.op("~")(r"^\d{4}-\d{2}-\d{2}$"), cast(raw_deadline, Date)), else_=None
    )
    active = and_(
        SourceRevision.current.is_(True), Document.status == "completed", ranked.c.rank == 1
    )
    done = case(
        (
            AnalysisItem.kind == "obligation",
            AnalysisItem.obligation_status.in_(["completed", "dismissed"]),
        ),
        else_=AnalysisItem.review_status.in_(["approved", "rejected"]),
    )
    return (
        select(
            AnalysisItem.id,
            AnalysisItem.run_id,
            AnalysisItem.kind,
            AnalysisItem.name,
            AnalysisItem.original,
            AnalysisItem.corrected,
            AnalysisItem.evidence,
            AnalysisItem.validation,
            AnalysisItem.review_status,
            AnalysisItem.obligation_status,
            func.coalesce(
                AnalysisItem.corrected["validation"].astext, AnalysisItem.validation
            ).label("effective_validation"),
            AnalysisItem.version,
            AnalysisItem.assignment_due_date,
            AnalysisItem.assignee_membership_id,
            SourceRevision.document_id,
            SourceRevision.id.label("revision_id"),
            Document.filename,
            AnalysisRun.engine,
            AnalysisRun.created_at,
            AnalysisTemplate.name.label("template_name"),
            ranked.c.family_id,
            active.label("is_current"),
            (ranked.c.rank > 1).label("analysis_superseded"),
            or_(SourceRevision.current.is_(False), Document.status != "completed").label(
                "source_superseded"
            ),
            member.user_id.label("assignee_id"),
            person.name.label("assignee_name"),
            AnalysisItem.original["severity"].astext.label("severity"),
            AnalysisItem.original["responsible_party"].astext.label("responsible_party"),
            deadline.label("contract_deadline"),
            done.label("is_done"),
            case((done, completion), else_=None).label("completed_at"),
        )
        .select_from(AnalysisItem)
        .join(
            AnalysisRun,
            and_(
                AnalysisRun.id == AnalysisItem.run_id,
                AnalysisRun.organization_id == org,
            ),
        )
        .join(ranked, ranked.c.run_id == AnalysisRun.id)
        .join(
            SourceRevision,
            and_(
                SourceRevision.id == AnalysisRun.left_revision_id,
                SourceRevision.organization_id == org,
            ),
        )
        .join(
            Document,
            and_(
                Document.id == SourceRevision.document_id,
                Document.organization_id == org,
                Document.deleted_at.is_(None),
            ),
        )
        .join(AnalysisTemplate, AnalysisTemplate.id == AnalysisRun.template_id)
        .outerjoin(
            member,
            and_(member.id == AnalysisItem.assignee_membership_id, member.organization_id == org),
        )
        .outerjoin(person, person.id == member.user_id)
        .where(
            AnalysisItem.organization_id == org,
            AnalysisItem.kind.in_(["field", "risk", "obligation"]),
        )
        .cte("portfolio")
    )


def metric_conditions(c, as_of):
    return {
        "records": true(),
        "risks": c.kind == "risk",
        "obligations": c.kind == "obligation",
        "pending_reviews": and_(
            c.kind.in_(["field", "risk"]), c.review_status.in_(["pending", "corrected"])
        ),
        "open_obligations": and_(c.kind == "obligation", ~c.is_done),
        "overdue_obligations": and_(
            c.kind == "obligation", ~c.is_done, c.contract_deadline < as_of
        ),
        "upcoming_obligations": and_(
            c.kind == "obligation",
            ~c.is_done,
            c.contract_deadline.between(as_of, as_of + timedelta(days=7)),
        ),
        "open_assignments": and_(c.assignee_id.is_not(None), ~c.is_done),
        "unresolved": c.effective_validation.in_(
            ["invalid", "ambiguous", "missing_required", "not_found", "manual_assertion"]
        ),
    }


def filtered(org, filters):
    rows = portfolio(org)
    c, conditions = rows.c, []
    if filters.focus:
        conditions.append(metric_conditions(c, filters.as_of)[filters.focus])
    if filters.scope != "all":
        conditions.append(c.is_current if filters.scope == "current" else ~c.is_current)
    if filters.engine != "all":
        conditions.append(c.engine == filters.engine)
    if filters.kind == "review":
        conditions.extend(
            [c.kind.in_(["field", "risk"]), c.review_status.in_(["pending", "corrected"])]
        )
    elif filters.kind:
        conditions.append(c.kind == filters.kind)
    for key, column in [
        ("document_id", c.document_id),
        ("review_status", c.review_status),
        ("obligation_status", c.obligation_status),
        ("severity", c.severity),
        ("assignee_id", c.assignee_id),
    ]:
        if getattr(filters, key) is not None:
            conditions.append(column == getattr(filters, key))
    if filters.party.strip():
        conditions.append(c.responsible_party.icontains(filters.party.strip(), autoescape=True))
    if filters.unassigned:
        conditions.append(c.assignee_id.is_(None))
    if filters.work_status:
        conditions.append(c.is_done if filters.work_status == "done" else ~c.is_done)
    if filters.unresolved:
        conditions.append(
            c.effective_validation.in_(
                ["invalid", "ambiguous", "missing_required", "not_found", "manual_assertion"]
            )
        )
    if filters.timing or filters.deadline_from or filters.deadline_to:
        conditions.append(c.kind == "obligation")
    if filters.deadline_from:
        conditions.append(c.contract_deadline >= filters.deadline_from)
    if filters.deadline_to:
        conditions.append(c.contract_deadline <= filters.deadline_to)
    for timing, column in [
        (filters.timing, c.contract_deadline),
        (filters.assignment_timing, c.assignment_due_date),
    ]:
        if timing == "unknown":
            conditions.append(column.is_(None))
        elif timing:
            conditions.append(~c.is_done)
            conditions.append(
                column < filters.as_of
                if timing == "overdue"
                else and_(
                    column >= filters.as_of,
                    column <= filters.as_of + timedelta(days=7),
                )
            )
    return select(rows).where(*conditions)


def current_item(db, org, item_id):
    rows = portfolio(org)
    return bool(db.scalar(select(rows.c.is_current).where(rows.c.id == item_id)))
