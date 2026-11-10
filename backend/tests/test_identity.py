import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import digest, now, passwords
from app.models import AuthSession, RefreshToken, User

PASSWORD = "correct horse battery staple"


def post(client, path, data=None, method="POST"):
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    return client.request(method, "/api/v1" + path, json=data, headers={"X-CSRF-Token": token})


def register(client, email="alice@example.com", name="Alice"):
    response = post(client, "/auth/register", {"email": email, "name": name, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def organization(client, name="Research"):
    response = post(client, "/organizations", {"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_registration_hashes_password_and_sets_httponly_cookies(clients, identity_db):
    client = clients()
    user = register(client, "ALICE@example.com")
    assert user["email"] == "alice@example.com"
    assert "password" not in str(user)
    assert client.get("/api/v1/auth/me").json() == user
    with Session(identity_db) as db:
        stored = db.scalar(select(User))
        assert stored.password_hash.startswith("$argon2id$")
        assert passwords.verify(PASSWORD, stored.password_hash)
        refresh = db.scalar(select(RefreshToken))
        assert refresh.token_hash == digest(client.cookies["dm_refresh"])
        assert PASSWORD not in stored.password_hash
    response = post(client, "/auth/login", {"email": user["email"], "password": PASSWORD})
    for header in response.headers.get_list("set-cookie"):
        assert "HttpOnly" in header and "SameSite=lax" in header and "Path=/" in header
        assert "Domain=" not in header


def test_registration_validation_does_not_echo_password(clients):
    client = clients()
    register(client)
    duplicate = post(
        client,
        "/auth/register",
        {"email": "alice@example.com", "name": "Alice", "password": PASSWORD},
    )
    assert duplicate.status_code == 409
    response = post(client, "/auth/register", {"email": "bad", "name": " ", "password": "private"})
    assert response.status_code == 422
    assert "private" not in response.text


def test_login_and_account_throttling(clients):
    client = clients()
    register(client)
    for _ in range(5):
        assert (
            post(
                client, "/auth/login", {"email": "alice@example.com", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        post(
            client, "/auth/login", {"email": "alice@example.com", "password": PASSWORD}
        ).status_code
        == 429
    )
    assert (
        post(
            client, "/auth/login", {"email": "unknown@example.com", "password": "wrong"}
        ).status_code
        == 401
    )


def test_csrf_required_for_login_registration_and_org_changes(clients):
    client = clients()
    data = {"email": "alice@example.com", "name": "Alice", "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=data).status_code == 403
    token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    assert (
        client.post(
            "/api/v1/auth/register",
            json=data,
            headers={"X-CSRF-Token": token, "Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    register(client)
    assert client.post("/api/v1/organizations", json={"name": "Test"}).status_code == 403
    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post("/api/v1/auth/refresh").status_code == 403


def test_csrf_is_signed_and_session_bound(clients):
    first, second = clients(), clients()
    register(first)
    register(second, "bob@example.com", "Bob")
    stolen = first.get("/api/v1/auth/csrf").json()["csrf_token"]
    second.cookies.set("dm_csrf", stolen, domain="localhost.local", path="/")
    response = second.post(
        "/api/v1/organizations", json={"name": "Forged"}, headers={"X-CSRF-Token": stolen}
    )
    assert response.status_code == 403


def test_refresh_rotation_replay_revokes_access_and_entire_family(clients, identity_db):
    client = clients()
    register(client)
    old_refresh = client.cookies["dm_refresh"]
    old_access = client.cookies["dm_access"]
    assert post(client, "/auth/refresh").status_code == 200
    replacement = client.cookies["dm_refresh"]
    assert replacement != old_refresh
    with Session(identity_db) as db:
        old = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == digest(old_refresh)))
        assert old.consumed_at is not None
    replay = clients()
    replay.cookies.set("dm_refresh", old_refresh)
    assert post(replay, "/auth/refresh").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert post(client, "/auth/refresh").status_code == 401
    assert old_access


def test_unknown_refresh_verifier_does_not_revoke_session(clients):
    client = clients()
    register(client)
    sid = client.cookies["dm_refresh"].split(".")[0]
    attacker = clients()
    attacker.cookies.set("dm_refresh", sid + ".not-a-valid-verifier")
    assert post(attacker, "/auth/refresh").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 200


def test_logout_revokes_copied_access_and_clears_cookies(clients):
    client = clients()
    register(client)
    stolen = clients()
    stolen.cookies.set("dm_access", client.cookies["dm_access"])
    assert post(client, "/auth/logout").status_code == 204
    assert "dm_refresh" not in client.cookies and "dm_access" not in client.cookies
    assert stolen.get("/api/v1/auth/me").status_code == 401


def test_access_expiry_signature_and_refresh_absolute_expiry(clients, identity_db):
    client = clients()
    register(client)
    token = client.cookies["dm_access"]
    payload = jwt.decode(token, options={"verify_signature": False})
    payload["exp"] = now() - timedelta(seconds=1)
    expired = jwt.encode(payload, "test-only-signing-key-" + "x" * 40, algorithm="HS256")
    stale = clients()
    stale.cookies.set("dm_access", expired)
    assert stale.get("/api/v1/auth/me").status_code == 401
    stale.cookies.clear()
    stale.cookies.set("dm_access", token + "tampered")
    assert stale.get("/api/v1/auth/me").status_code == 401
    with Session(identity_db) as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert post(client, "/auth/refresh").status_code == 401


def test_production_cookies_are_secure_host_only(clients):
    client = clients(secure=True)
    response = post(
        client,
        "/auth/register",
        {"email": "alice@example.com", "name": "Alice", "password": PASSWORD},
    )
    assert response.status_code == 201
    for cookie in response.headers.get_list("set-cookie"):
        assert cookie.startswith("__Host-dm_")
        assert "Secure" in cookie and "HttpOnly" in cookie and "Domain=" not in cookie


def test_multi_organization_roles_and_cross_organization_isolation(clients):
    alice, bob, outsider = clients(), clients(), clients()
    register(alice)
    bob_user = register(bob, "bob@example.com", "Bob")
    register(outsider, "outside@example.com", "Outside")
    org_a = organization(alice, "Alice team")
    org_b = organization(bob, "Bob team")
    assert (
        post(
            alice, f"/organizations/{org_a}/members", {"email": "bob@example.com", "role": "member"}
        ).status_code
        == 201
    )
    roles = {org["id"]: org["role"] for org in bob.get("/api/v1/organizations").json()}
    assert roles == {org_a: "member", org_b: "admin"}
    assert bob.get(f"/api/v1/organizations/{org_a}/members").status_code == 200
    assert (
        post(
            bob,
            f"/organizations/{org_a}/members",
            {"email": "outside@example.com", "role": "admin"},
        ).status_code
        == 403
    )
    assert alice.get(f"/api/v1/organizations/{org_b}").status_code == 404
    for path in [f"/organizations/{org_a}", f"/organizations/{org_a}/members"]:
        assert outsider.get("/api/v1" + path).status_code == 404
    assert (
        post(
            alice, f"/organizations/{org_b}/members/{bob_user['id']}", {"role": "member"}, "PATCH"
        ).status_code
        == 404
    )
    assert (
        post(alice, f"/organizations/{org_b}/members/{bob_user['id']}", method="DELETE").status_code
        == 404
    )


def test_last_admin_duplicate_members_and_immediate_role_changes(clients):
    alice, bob = clients(), clients()
    a = register(alice)
    b = register(bob, "bob@example.com", "Bob")
    org = organization(alice)
    path = f"/organizations/{org}/members"
    assert post(alice, path + f"/{a['id']}", {"role": "member"}, "PATCH").status_code == 409
    assert post(alice, path + f"/{a['id']}", method="DELETE").status_code == 409
    assert post(alice, path, {"email": b["email"], "role": "member"}).status_code == 201
    assert post(alice, path, {"email": b["email"], "role": "member"}).status_code == 409
    assert post(alice, path + f"/{b['id']}", {"role": "admin"}, "PATCH").status_code == 200
    assert post(bob, path + f"/{a['id']}", {"role": "member"}, "PATCH").status_code == 200
    assert post(alice, path + f"/{b['id']}", {"role": "member"}, "PATCH").status_code == 403
    assert post(bob, path + f"/{a['id']}", method="DELETE").status_code == 204
    assert alice.get(f"/api/v1/organizations/{org}/members").status_code == 404
    assert alice.get("/api/v1/organizations").json() == []


def test_concurrent_refresh_consumes_once_and_detects_replay(clients):
    original = clients()
    register(original)
    token = original.cookies["dm_refresh"]
    barrier = Barrier(2)
    workers = [clients(), clients()]
    for worker in workers:
        worker.cookies.set("dm_refresh", token)

    def refresh(worker):
        csrf = worker.get("/api/v1/auth/csrf").json()["csrf_token"]
        barrier.wait(timeout=10)
        return worker.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(refresh, workers))
    assert sorted(results) == [200, 401]
    assert original.get("/api/v1/auth/me").status_code == 401


def test_concurrent_admin_demotions_preserve_one_admin(clients):
    alice, bob = clients(), clients()
    a = register(alice)
    b = register(bob, "bob@example.com", "Bob")
    org = organization(alice)
    path = f"/organizations/{org}/members"
    assert post(alice, path, {"email": b["email"], "role": "admin"}).status_code == 201
    barrier = Barrier(2)

    def demote(args):
        client, user_id = args
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        barrier.wait(timeout=10)
        return client.patch(
            "/api/v1" + path + f"/{user_id}",
            json={"role": "member"},
            headers={"X-CSRF-Token": csrf},
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(demote, [(alice, a["id"]), (bob, b["id"])]))
    assert sorted(results) == [200, 409]


def test_unauthenticated_organization_reads_are_denied(clients):
    client = clients()
    assert client.get("/api/v1/organizations").status_code == 401
    assert client.get(f"/api/v1/organizations/{uuid.uuid4()}/members").status_code == 401


def test_admin_can_leave_when_another_admin_remains(clients):
    alice, bob = clients(), clients()
    a = register(alice)
    b = register(bob, "bob@example.com", "Bob")
    org = organization(alice)
    path = f"/organizations/{org}/members"
    assert post(alice, path, {"email": b["email"], "role": "admin"}).status_code == 201
    assert post(alice, path + f"/{a['id']}", method="DELETE").status_code == 204
    assert alice.get("/api/v1/organizations").json() == []
    assert alice.get(f"/api/v1/organizations/{org}").status_code == 404
    assert bob.get(f"/api/v1/organizations/{org}/members").json()[0]["user_id"] == b["id"]
