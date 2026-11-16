import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import now
from app.documents.worker import run_once
from app.models import AnalysisItem, AnalysisRun, Document, DocumentJob, ReviewEvent, SourceRevision
from app.structured.engine import analyze, normalize
from app.structured.schemas import TemplateInput
from app.structured.worker import run_analysis_once
from tests.test_documents import account, mutate, organization, upload

TEXT = (
    b"Party: Acme Ltd\nEffective Date: 2026-11-01\nFee: USD 15000\n"
    b"Acme shall deliver reports by 2026-12-01.\nSupplier accepts unlimited liability.\n"
)
TEMPLATE = {
    "name": "Contract facts",
    "fields": [
        {"name": "party", "type": "text", "label": "Party", "required": True},
        {"name": "date", "type": "date", "label": "Effective Date", "required": True},
        {"name": "fee", "type": "money", "label": "Fee"},
        {"name": "missing", "type": "text", "label": "Not Present", "required": True},
    ],
    "rules": [
        {
            "name": "Liability candidate",
            "type": "contains",
            "term": "unlimited liability",
            "severity": "high",
        },
        {"name": "Termination not detected", "type": "missing", "term": "termination"},
        {"name": "High fee", "type": "threshold", "field": "fee", "threshold": 10000},
    ],
    "obligations": True,
}


@pytest.fixture
def structured(clients, identity_db):
    client = clients(llm_provider="mock")
    account(client)
    org = organization(client)
    doc = upload(client, org, TEXT).json()["id"]
    assert run_once(identity_db, client.app.state.settings)
    base = f"/organizations/{org}/structured"
    template = mutate(client, base + "/templates", TEMPLATE)
    assert template.status_code == 201, template.text
    return client, org, doc, base, template.json()["id"]


def submit(fixture, identity_db, **kwargs):
    client, _, doc, base, template = fixture
    response = mutate(
        client, base + "/runs", {"document_id": doc, "template_id": template, **kwargs}
    )
    assert response.status_code == 202, response.text
    assert run_analysis_once(identity_db, client.app.state.settings)
    run_id = response.json()["id"]
    output = client.get("/api/v1" + base + f"/runs/{run_id}")
    assert output.status_code == 200, output.text
    return run_id, output.json()


@pytest.mark.parametrize(
    "raw,kind,value,state",
    [
        ("2026-11-01", "date", "2026-11-01", "valid"),
        ("01/02/26", "date", None, "invalid"),
        ("USD 15000", "money", {"currency": "USD", "amount": "15000"}, "valid"),
        ("USD 50,000", "money", {"currency": "USD", "amount": "50000"}, "valid"),
        ("USD 1,234,567.89", "money", {"currency": "USD", "amount": "1234567.89"}, "valid"),
        ("USD -50,000.25", "money", {"currency": "USD", "amount": "-50000.25"}, "valid"),
        ("USD 50,00", "money", None, "invalid"),
        ("USD 50,0000", "money", None, "invalid"),
        ("USD 50.000,00", "money", None, "invalid"),
        ("USD 1,,000", "money", None, "invalid"),
        ("$500", "money", None, "invalid"),
        ("NaN", "decimal", None, "invalid"),
        ("yes", "boolean", True, "valid"),
        ("one;two", "list", ["one", "two"], "valid"),
    ],
)
def test_typed_values(raw, kind, value, state):
    assert normalize(raw, kind) == (value, state)


def test_schema_and_resource_limits():
    with pytest.raises(ValueError):
        TemplateInput.model_validate({**TEMPLATE, "fields": [TEMPLATE["fields"][0]] * 2})
    section = SimpleNamespace(text="x" * 1001)
    with pytest.raises(ValueError, match="no partial"):
        analyze(
            [section],
            [],
            {},
            "extract",
            "deterministic",
            SimpleNamespace(analysis_max_characters=1000),
        )


@pytest.mark.parametrize("threshold,expected_risks", [(40000, 1), (50000, 0), (60000, 0)])
def test_grouped_money_threshold_persisted_with_source(
    structured, identity_db, threshold, expected_risks
):
    client, org, _, base, _ = structured
    source = "Contract value: USD 50,000"
    doc = upload(client, org, source.encode()).json()["id"]
    assert run_once(identity_db, client.app.state.settings)
    template = mutate(
        client,
        base + "/templates",
        {
            "name": "Grouped contract value",
            "fields": [
                {
                    "name": "contract_value",
                    "type": "money",
                    "label": "Contract Value",
                    "required": True,
                }
            ],
            "rules": [
                {
                    "name": "Contract value above limit",
                    "type": "threshold",
                    "term": "",
                    "field": "contract_value",
                    "severity": "medium",
                    "threshold": threshold,
                }
            ],
            "obligations": False,
        },
    )
    assert template.status_code == 201
    fixture = (client, org, doc, base, template.json()["id"])
    run_id, output = submit(fixture, identity_db)
    assert output["run"]["state"] == "completed"
    field = next(item for item in output["items"] if item["kind"] == "field")
    assert field["validation"] == "valid"
    assert field["original"]["raw"] == "USD 50,000"
    assert field["original"]["value"] == {"currency": "USD", "amount": "50000"}
    risks = [item for item in output["items"] if item["kind"] == "risk"]
    assert len(risks) == expected_risks
    if risks:
        assert risks[0]["original"]["severity"] == "medium"
        assert risks[0]["evidence"][0]["quote"] == source
    exported = client.get(f"/api/v1{base}/runs/{run_id}/export?format=json").json()
    assert sum(item["kind"] == "risk" for item in exported["items"]) == expected_risks


def test_extraction_evidence_risks_obligations(structured, identity_db):
    client, _, _, base, _ = structured
    run_id, result = submit(structured, identity_db)
    assert result["run"]["state"] == "completed", result
    assert result["run"]["coverage"]["complete"] is True
    items = result["items"]
    fee = next(i for i in items if i["name"] == "fee")
    assert fee["original"]["value"] == {"currency": "USD", "amount": "15000"}
    assert fee["evidence"][0]["quote"] == "Fee: USD 15000"
    missing = next(i for i in items if i["name"] == "missing")
    assert missing["validation"] == "missing_required" and not missing["evidence"]
    risks = [i for i in items if i["kind"] == "risk"]
    assert len(risks) == 3
    absence = next(i for i in risks if i["validation"] == "coverage_only")
    assert not absence["evidence"] and "not proof" in absence["original"]["note"]
    obligation = next(i for i in items if i["kind"] == "obligation")
    assert obligation["original"]["deadline"] == "2026-12-01"
    assert obligation["original"]["responsible_party"] == "Acme"
    content = client.get(
        f"/api/v1{base}/runs/{run_id}/sections",
        params={
            "revision_id": result["run"]["left_revision_id"],
        },
    ).json()["items"][0]["text"]
    for item in items:
        for evidence in item["evidence"]:
            assert content[evidence["start"] : evidence["end"]] == evidence["quote"]


def test_mock_labeled_and_deterministic_output(structured, identity_db):
    _, output = submit(structured, identity_db, engine="mock")
    assert output["run"]["engine"] == "mock"
    assert any(
        i["name"] == "party" and i["original"]["value"] == "Acme Ltd" for i in output["items"]
    )


def test_review_history_conflicts_and_manual_values(structured, identity_db):
    client, _, _, base, _ = structured
    run_id, result = submit(structured, identity_db)
    item = next(i for i in result["items"] if i["name"] == "party")
    path = base + f"/runs/{run_id}/items/{item['id']}/review"
    assert (
        mutate(
            client, path, {"version": 1, "action": "approve", "reason": "Checked source"}
        ).status_code
        == 200
    )
    assert (
        mutate(client, path, {"version": 1, "action": "reject", "reason": "Stale"}).status_code
        == 409
    )
    assert (
        mutate(
            client, path, {"version": 2, "action": "correct", "reason": "Manual", "value": "Other"}
        ).status_code
        == 200
    )
    assert (
        mutate(
            client, path, {"version": 3, "action": "approve", "reason": "No support"}
        ).status_code
        == 422
    )
    forged = {**item["evidence"][0], "quote": "Forged"}
    assert (
        mutate(
            client,
            path,
            {
                "version": 3,
                "action": "correct",
                "reason": "Bad evidence",
                "value": "Other",
                "evidence": forged,
            },
        ).status_code
        == 422
    )
    assert (
        mutate(
            client,
            path,
            {
                "version": 3,
                "action": "correct",
                "reason": "Literal correction",
                "value": "Acme",
                "evidence": item["evidence"][0],
            },
        ).status_code
        == 200
    )
    fresh = client.get(f"/api/v1{base}/runs/{run_id}").json()
    assert len(fresh["reviews"]) == 3
    assert (
        next(i for i in fresh["items"] if i["id"] == item["id"])["original"]["value"] == "Acme Ltd"
    )


def test_reprocess_preserves_reviews_and_old_revision(structured, identity_db):
    client, org, doc_id, base, _ = structured
    run_id, result = submit(structured, identity_db)
    item = next(i for i in result["items"] if i["name"] == "party")
    mutate(
        client,
        base + f"/runs/{run_id}/items/{item['id']}/review",
        {"version": 1, "action": "approve", "reason": "Verified"},
    )
    with Session(identity_db) as db:
        document = db.get(Document, uuid.UUID(doc_id))
        document.status = "failed"
        job = db.scalar(select(DocumentJob).where(DocumentJob.document_id == document.id))
        job.state = "failed"
        db.commit()
    assert mutate(client, f"/organizations/{org}/documents/{doc_id}/retry").status_code == 202
    assert run_once(identity_db, client.app.state.settings)
    fresh = client.get(f"/api/v1{base}/runs/{run_id}").json()
    assert fresh["superseded"] is True
    assert next(i for i in fresh["items"] if i["id"] == item["id"])["review_status"] == "approved"
    assert len(fresh["reviews"]) == 1
    revisions = client.get(f"/api/v1{base}/documents/{doc_id}/revisions").json()
    assert len(revisions) == 2
    _, comparison = submit(
        structured,
        identity_db,
        mode="compare",
        other_document_id=doc_id,
        revision_id=revisions[1]["id"],
        other_revision_id=revisions[0]["id"],
    )
    assert comparison["run"]["state"] == "completed" and comparison["items"] == []


def test_comparison_with_exact_sources(structured, identity_db):
    client, org, _, _, _ = structured
    other = upload(
        client, org, TEXT.replace(b"USD 15000", b"USD 25000") + b"Termination: thirty days\n"
    ).json()["id"]
    run_once(identity_db, client.app.state.settings)
    _, output = submit(structured, identity_db, mode="compare", other_document_id=other)
    assert output["run"]["state"] == "completed"
    assert any(i["name"] == "Modified" and len(i["evidence"]) == 2 for i in output["items"])
    assert any(i["name"] == "Added" for i in output["items"])


def test_permissions_exports_and_template_versions(structured, clients, identity_db):
    client, org, doc, base, template = structured
    run_id, _ = submit(structured, identity_db)
    other = clients()
    account(other, "Bob")
    other_org = organization(other, "Other")
    assert other.get(f"/api/v1{base}/runs/{run_id}/export").status_code == 404
    assert (
        mutate(
            other,
            f"/organizations/{other_org}/structured/runs",
            {"document_id": doc, "template_id": template},
        ).status_code
        == 404
    )
    mutate(client, f"/organizations/{org}/members", {"email": "bob@example.com", "role": "member"})
    assert other.get(f"/api/v1{base}/runs/{run_id}").status_code == 200
    assert (
        mutate(other, base + "/runs", {"document_id": doc, "template_id": template}).status_code
        == 403
    )
    assert mutate(other, base + "/templates", TEMPLATE).status_code == 403
    version = mutate(client, base + "/templates", {**TEMPLATE, "parent_id": template, "name": "v2"})
    assert version.status_code == 201 and version.json()["id"] != template
    for fmt in ["json", "csv"]:
        response = client.get(f"/api/v1{base}/runs/{run_id}/export?format={fmt}")
        assert (
            response.status_code == 200 and "attachment" in response.headers["content-disposition"]
        )


def test_deletion_purges_retained_content_but_keeps_audit(structured, identity_db):
    client, org, doc, base, _ = structured
    run_id, result = submit(structured, identity_db)
    item = result["items"][0]
    mutate(
        client,
        base + f"/runs/{run_id}/items/{item['id']}/review",
        {"version": 1, "action": "reject", "reason": "Private reviewer note"},
    )
    assert (
        mutate(client, f"/organizations/{org}/documents/{doc}", method="DELETE").status_code == 202
    )
    assert client.get(f"/api/v1{base}/runs/{run_id}").status_code == 410
    assert client.get(f"/api/v1{base}/runs/{run_id}/export").status_code == 410
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(SourceRevision)) == 0
        assert all(i.original == {} and i.evidence == [] for i in db.scalars(select(AnalysisItem)))
        event = db.scalar(select(ReviewEvent))
        assert event.before == {"version": 1} and event.after == {"version": 2}
        assert "Private" not in event.reason
    assert run_once(identity_db, client.app.state.settings)


def test_analysis_recovery_and_failure_without_partial_results(structured, identity_db):
    client, _, doc, base, template = structured
    response = mutate(client, base + "/runs", {"document_id": doc, "template_id": template})
    run_id = uuid.UUID(response.json()["id"])
    with Session(identity_db) as db:
        run = db.get(AnalysisRun, run_id)
        run.state, run.attempts = "processing", 1
        run.lease_token, run.lease_until = uuid.uuid4(), now() - timedelta(seconds=1)
        db.commit()
    assert run_analysis_once(identity_db, client.app.state.settings)
    assert client.get(f"/api/v1{base}/runs/{run_id}").json()["run"]["state"] == "completed"
    client.app.state.settings.analysis_max_characters = 1
    _, failed = submit(structured, identity_db)
    assert failed["run"]["state"] == "failed" and not failed["items"]


def test_obligation_status_and_csv_formula_safety(structured, identity_db):
    from app.api.routes.structured import csv_safe

    assert csv_safe("  =HYPERLINK(1)").startswith("'")
    client, _, _, base, _ = structured
    run_id, result = submit(structured, identity_db)
    obligation = next(i for i in result["items"] if i["kind"] == "obligation")
    path = base + f"/runs/{run_id}/items/{obligation['id']}/review"
    response = mutate(
        client,
        path,
        {
            "version": 1,
            "action": "obligation",
            "reason": "Delivered",
            "obligation_status": "completed",
        },
    )
    assert response.status_code == 200
    items = client.get(f"/api/v1{base}/obligations?status=completed").json()
    assert len(items) == 1 and items[0]["original"]["deadline"] == "2026-12-01"


def test_deletion_during_analysis_cannot_publish(structured, identity_db, monkeypatch):
    from app.documents.service import queue_deletion
    from app.structured.engine import analyze as real_analyze

    client, _, doc, base, template = structured
    response = mutate(client, base + "/runs", {"document_id": doc, "template_id": template})

    def remove_source(*args):
        result = real_analyze(*args)
        with Session(identity_db) as db:
            queue_deletion(db, db.get(Document, uuid.UUID(doc)))
        return result

    monkeypatch.setattr("app.structured.worker.analyze", remove_source)
    assert run_analysis_once(identity_db, client.app.state.settings)
    with Session(identity_db) as db:
        run = db.get(AnalysisRun, uuid.UUID(response.json()["id"]))
        assert run.state == "unavailable"
        assert db.scalar(select(func.count()).select_from(AnalysisItem)) == 0


def test_stale_worker_result_is_fenced(structured, identity_db, monkeypatch):
    from app.structured.engine import analyze as real_analyze

    client, _, doc, base, template = structured
    response = mutate(client, base + "/runs", {"document_id": doc, "template_id": template})
    run_id = uuid.UUID(response.json()["id"])

    def supersede(*args):
        result = real_analyze(*args)
        with Session(identity_db) as db:
            run = db.get(AnalysisRun, run_id)
            run.lease_token = uuid.uuid4()
            db.commit()
        return result

    monkeypatch.setattr("app.structured.worker.analyze", supersede)
    assert run_analysis_once(identity_db, client.app.state.settings)
    with Session(identity_db) as db:
        assert db.scalar(select(func.count()).select_from(AnalysisItem)) == 0
