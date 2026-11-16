import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.worker import run_once
from app.models import Document, DocumentJob
from tests.test_documents import account, mutate, organization
from tests.test_structured import TEMPLATE, submit
from tests.test_structured import structured as structured


def base(fixture):
    return f"/organizations/{fixture[1]}/operations"


def response(client, path):
    result = client.get("/api/v1" + path)
    assert result.status_code == 200, result.text
    return result.json()


def test_latest_runs_versions_and_independent_families(structured, identity_db):
    client, _, doc, structured_base, template = structured
    submit(structured, identity_db)
    run, original = submit(structured, identity_db)
    path = base(structured)
    summary = response(client, path + "/summary")
    count = len(original["items"])
    assert summary["totals"]["records"] == count
    assert response(client, path + "/items")["total"] == count
    assert response(client, path + "/items?scope=superseded")["total"] == count
    child = mutate(
        client, structured_base + "/templates", {**TEMPLATE, "parent_id": template}
    ).json()["id"]
    submit((client, structured[1], doc, structured_base, child), identity_db)
    assert response(client, path + "/summary")["totals"]["records"] == count
    independent = mutate(client, structured_base + "/templates", TEMPLATE).json()["id"]
    submit((client, structured[1], doc, structured_base, independent), identity_db)
    assert response(client, path + "/summary")["totals"]["records"] == count * 2
    assert response(client, path + "/export?format=json")["total"] == count * 2
    assert "not unique" in summary["counting"]


def test_filters_totals_exports_and_deadlines(structured, identity_db):
    client = structured[0]
    submit(structured, identity_db)
    path = base(structured)
    params = "?kind=obligation&as_of=2026-12-02&timing=overdue&party=Acme"
    assert response(client, path + "/items" + params)["total"] == 1
    assert response(client, path + "/summary" + params)["totals"]["overdue_obligations"] == 1
    assert response(client, path + "/export" + params)["total"] == 1
    assert (
        response(client, path + "/items?kind=obligation&as_of=2026-12-01&timing=overdue")["total"]
        == 0
    )
    assert (
        response(client, path + "/items?kind=obligation&as_of=2026-12-01&timing=upcoming")["total"]
        == 1
    )
    assert response(client, path + "/items?kind=obligation&deadline_from=2026-12-02")["total"] == 0
    assert response(client, path + "/items?timing=unknown")["total"] == 0
    assert (
        client.get(
            "/api/v1" + path + "/items?deadline_from=2027-01-01&deadline_to=2026-01-01"
        ).status_code
        == 422
    )
    risks = response(client, path + "/items?kind=risk&severity=high")
    assert risks["total"] == 1
    assert response(client, path + "/summary?kind=risk&severity=high")["totals"]["risks"] == 1
    totals = response(client, path + "/summary?as_of=2026-12-02")["totals"]
    for metric, value in totals.items():
        query = f"?as_of=2026-12-02&focus={metric}"
        assert response(client, path + "/items" + query)["total"] == value
        assert response(client, path + "/export" + query)["total"] == value


def add_bob(fixture, clients):
    client, org, *_ = fixture
    bob = clients()
    user = account(bob, "Bob")
    added = mutate(
        client, f"/organizations/{org}/members", {"email": "bob@example.com", "role": "member"}
    )
    assert added.status_code == 201
    return bob, user["id"]


def test_assignment_delegates_only_item_and_preserves_contract_date(
    structured, clients, identity_db
):
    client = structured[0]
    run_id, _ = submit(structured, identity_db)
    bob, bob_id = add_bob(structured, clients)
    path = base(structured)
    obligation = response(client, path + "/items?kind=obligation")["items"][0]
    assignment = path + f"/items/{obligation['id']}/assignment"
    payload = {"version": obligation["version"], "assignee_id": bob_id, "due_date": "2026-11-25"}
    assert mutate(bob, assignment, payload, method="PATCH").status_code == 403
    assert mutate(client, assignment, payload, method="PATCH").status_code == 200
    assert mutate(client, assignment, payload, method="PATCH").status_code == 409
    current = response(bob, path + f"/items?assignee_id={bob_id}")["items"][0]
    assert current["assignment_due_date"] == "2026-11-25"
    assert current["contract_deadline"] == "2026-12-01"
    assert current["can_review"] and not current["can_assign"]
    review = structured[3] + f"/runs/{run_id}/items/{obligation['id']}/review"
    assert (
        mutate(
            bob,
            review,
            {
                "version": current["version"],
                "action": "obligation",
                "reason": "Delivered",
                "obligation_status": "completed",
            },
        ).status_code
        == 200
    )
    done = response(bob, path + "/items?kind=obligation")["items"][0]
    assert done["is_done"] and done["completed_at"]
    assert response(client, path + "/summary?kind=obligation")["totals"]["open_obligations"] == 0
    field = response(client, path + "/items?kind=field")["items"][0]
    assert (
        mutate(
            bob,
            structured[3] + f"/runs/{run_id}/items/{field['id']}/review",
            {"version": field["version"], "action": "reject", "reason": "Not assigned"},
        ).status_code
        == 403
    )


def test_membership_removal_clears_assignments_and_preserves_identity(
    structured, clients, identity_db
):
    client, org, *_ = structured
    submit(structured, identity_db)
    bob, bob_id = add_bob(structured, clients)
    path = base(structured)
    field = response(client, path + "/items?kind=field")["items"][0]
    assert (
        mutate(
            client,
            path + f"/items/{field['id']}/assignment",
            {"version": field["version"], "assignee_id": bob_id},
            method="PATCH",
        ).status_code
        == 200
    )
    assert (
        mutate(client, f"/organizations/{org}/members/{bob_id}", method="DELETE").status_code == 204
    )
    item = next(i for i in response(client, path + "/items")["items"] if i["id"] == field["id"])
    assert item["assignee_id"] is None
    activity = response(client, path + f"/activity?item_id={field['id']}")["items"]
    assert activity[0]["action"] == "member_unassigned"
    assert activity[0]["before"]["assignee_id"] == bob_id
    assert activity[0]["actor_id"] and activity[0]["actor_name"]
    assert bob.get("/api/v1" + path + "/items").status_code == 404


def test_cross_org_assignment_and_mock_exclusion(structured, clients, identity_db):
    client = structured[0]
    submit(structured, identity_db)
    bob = clients()
    bob_id = account(bob, "Bob")["id"]
    org_b = organization(bob)
    path = base(structured)
    row = response(client, path + "/items")["items"][0]
    assert (
        mutate(
            client,
            path + f"/items/{row['id']}/assignment",
            {"version": row["version"], "assignee_id": bob_id},
            method="PATCH",
        ).status_code
        == 404
    )
    assert bob.get("/api/v1" + path + "/export").status_code == 404
    assert response(bob, f"/organizations/{org_b}/operations/summary")["totals"]["records"] == 0
    before = response(client, path + "/summary")["totals"]["records"]
    submit(structured, identity_db, engine="mock")
    assert response(client, path + "/summary")["totals"]["records"] == before
    assert response(client, path + "/items?engine=all")["total"] == before * 2


def test_reprocessing_and_deleted_sources_leave_no_portfolio_leaks(structured, identity_db):
    client, org, doc_id, *_ = structured
    submit(structured, identity_db)
    path = base(structured)
    with Session(identity_db) as db:
        document = db.get(Document, uuid.UUID(doc_id))
        document.status = "failed"
        job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == document.id))
        job.state = "failed"
        db.commit()
    assert mutate(client, f"/organizations/{org}/documents/{doc_id}/retry").status_code == 202
    assert run_once(identity_db, client.app.state.settings)
    assert response(client, path + "/items")["total"] == 0
    assert response(client, path + "/items?scope=superseded")["total"] > 0
    submit(structured, identity_db)
    assert (
        mutate(client, f"/organizations/{org}/documents/{doc_id}", method="DELETE").status_code
        == 202
    )
    assert response(client, path + "/items?scope=all")["total"] == 0
    assert response(client, path + "/export?scope=all")["total"] == 0
