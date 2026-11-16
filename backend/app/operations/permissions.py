from app.operations.queries import current_item


def manages(member, user, documents):
    return member.role == "admin" or all(document.uploader_id == user.id for document in documents)


def may_review(db, org, member, user, documents, item):
    return manages(member, user, documents) or (
        item.assignee_membership_id == member.id and current_item(db, org, item.id)
    )
