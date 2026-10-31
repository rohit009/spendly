import pytest

import database.db as db
from app import app as flask_app

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def session_user_id(client):
    with client.session_transaction() as sess:
        return sess.get("user_id")


def demo_id():
    conn = db.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    conn.close()
    return row["id"]


def test_get_login_renders_form(client):
    assert client.get("/login").status_code == 200


def test_valid_login_redirects_to_home_and_sets_session(client):
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert not resp.headers["Location"].endswith("/login")
    assert session_user_id(client) == demo_id()


def test_email_is_case_and_whitespace_insensitive(client):
    resp = login(client, email="  Demo@Spendly.com ")
    assert resp.status_code == 302
    assert session_user_id(client) == demo_id()


@pytest.mark.parametrize(
    "email, password",
    [(DEMO_EMAIL, "wrong-password"), ("nobody@example.com", DEMO_PASSWORD)],
)
def test_bad_credentials_rejected_with_generic_error(client, email, password):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    assert session_user_id(client) is None


@pytest.mark.parametrize(
    "email, password, message",
    [
        ("", DEMO_PASSWORD, b"enter your email"),
        (DEMO_EMAIL, "", b"enter your password"),
    ],
)
def test_empty_fields_rejected(client, email, password, message):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert message in resp.data
    assert session_user_id(client) is None


def test_failed_login_keeps_email_but_not_password(client):
    resp = login(client, email=DEMO_EMAIL, password="wrong-password")
    assert b'value="demo@spendly.com"' in resp.data
    assert b"wrong-password" not in resp.data


@pytest.mark.parametrize("path", ["/login", "/register"])
def test_auth_pages_redirect_home_when_already_logged_in(client, path):
    login(client)
    resp = client.get(path)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_register_post_blocked_when_logged_in(client):
    login(client)
    resp = client.post(
        "/register",
        data={"name": "X Y", "email": "x@example.com", "password": "password123"},
    )
    assert resp.status_code == 302
    conn = db.get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    assert count == 1


def test_logout_clears_session_and_redirects_to_landing(client):
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert session_user_id(client) is None


def test_logout_works_when_not_logged_in(client):
    resp = client.get("/logout")
    assert resp.status_code == 302


def test_navbar_reflects_login_state(client):
    logged_out = client.get("/").data
    assert b"Sign in" in logged_out
    assert b"Get started" in logged_out
    assert b"Sign out" not in logged_out

    login(client)
    logged_in = client.get("/").data
    assert b"Sign out" in logged_in
    assert b"Get started" not in logged_in


def test_registered_user_can_log_in(client):
    client.post(
        "/register",
        data={"name": "Asha Rao", "email": "asha@example.com", "password": "password123"},
    )
    resp = login(client, email="asha@example.com", password="password123")
    assert resp.status_code == 302
    assert session_user_id(client) is not None
