import pytest
from werkzeug.security import check_password_hash

import database.db as db
from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def user_rows():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return rows


def register(client, name="Asha Rao", email="asha@example.com", password="password123"):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password}
    )


def test_get_register_renders_form(client):
    assert client.get("/register").status_code == 200


def test_valid_registration_redirects_to_login(client):
    resp = register(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    rows = user_rows()
    assert len(rows) == 1
    assert rows[0]["name"] == "Asha Rao"
    assert rows[0]["email"] == "asha@example.com"


def test_password_is_hashed(client):
    register(client)
    stored = user_rows()[0]["password_hash"]
    assert stored != "password123"
    assert check_password_hash(stored, "password123")


def test_duplicate_email_rejected_case_insensitively(client):
    register(client, email="demo@spendly.com")
    resp = register(client, name="Other", email="Demo@Spendly.com")
    assert resp.status_code == 200
    assert b"already exists" in resp.data
    assert len(user_rows()) == 1


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"name": ""}, b"enter your name"),
        ({"name": "   "}, b"enter your name"),
        ({"email": ""}, b"valid email"),
        ({"email": "no-at-sign"}, b"valid email"),
        ({"email": "a@nodot"}, b"valid email"),
        ({"password": "short7!"}, b"at least 8 characters"),
    ],
)
def test_invalid_input_rejected(client, fields, message):
    resp = register(client, **fields)
    assert resp.status_code == 200
    assert message in resp.data
    assert user_rows() == []


def test_failed_submit_keeps_name_and_email_but_not_password(client):
    resp = register(client, name="Asha Rao", email="asha@example.com", password="short")
    assert b'value="Asha Rao"' in resp.data
    assert b'value="asha@example.com"' in resp.data
    assert b"short" not in resp.data
