from sqlalchemy import select

from app.models import AnalysisItem, Membership, ReviewEvent


def assignment_state(db, item):
    member = (
        db.get(Membership, item.assignee_membership_id) if item.assignee_membership_id else None
    )
    return {
        "assignee_id": str(member.user_id) if member else None,
        "due_date": item.assignment_due_date.isoformat() if item.assignment_due_date else None,
        "version": item.version,
    }


def assign(db, item, member, actor, due_date, action="assignment"):
    before = assignment_state(db, item)
    item.assignee_membership_id = member.id if member else None
    item.assignment_due_date = due_date
    item.version += 1
    db.add(
        ReviewEvent(
            item_id=item.id,
            actor_id=actor.id,
            action=action,
            before=before,
            after={
                "assignee_id": str(member.user_id) if member else None,
                "due_date": due_date.isoformat() if due_date else None,
                "version": item.version,
            },
            reason="Organization membership removed"
            if action == "member_unassigned"
            else "Assignment or workflow due date changed",
        )
    )


def clear_member_assignments(db, member, actor):
    items = db.scalars(
        select(AnalysisItem)
        .where(
            AnalysisItem.organization_id == member.organization_id,
            AnalysisItem.assignee_membership_id == member.id,
        )
        .order_by(AnalysisItem.id)
        .with_for_update()
    ).all()
    for item in items:
        assign(db, item, None, actor, None, action="member_unassigned")
