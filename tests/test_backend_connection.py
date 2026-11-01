import pytest

import database.db as db
from app import app as flask_app
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

DEMO_EMAIL = "demo@spendly.com"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def add_user(name="Asha Rao", email="asha@example.com"):
    conn = db.get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, "x"),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def add_expenses(user_id, rows):
    conn = db.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, *r) for r in rows],
    )
    conn.commit()
    conn.close()


def demo_id():
    conn = db.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    conn.close()
    return row["id"]


def login(client):
    client.post("/login", data={"email": DEMO_EMAIL, "password": "demo123"})


# ---------------------------------------------------------------- unit tests

def test_get_user_by_id_returns_profile_fields(client):
    user = get_user_by_id(demo_id())
    assert user["name"] == "Demo User"
    assert user["email"] == DEMO_EMAIL
    assert user["initials"] == "DU"
    assert len(user["member_since"].split()) == 2  # "Month YYYY"


def test_get_user_by_id_missing_returns_none(client):
    assert get_user_by_id(9999) is None


def test_summary_stats_for_seed_user(client):
    assert get_summary_stats(demo_id()) == {
        "total_spent": 6948.0,
        "transaction_count": 8,
        "top_category": "Shopping",
    }


def test_summary_stats_empty_user(client):
    uid = add_user()
    assert get_summary_stats(uid) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_recent_transactions_newest_first_with_formatted_fields(client):
    uid = add_user()
    add_expenses(
        uid,
        [
            (100, "Food", "2026-01-05", "Old"),
            (300, "Bills", "2026-03-20", "Newest"),
            (200, "Other", "2026-02-10", "Middle"),
        ],
    )
    rows = get_recent_transactions(uid)
    assert [r["description"] for r in rows] == ["Newest", "Middle", "Old"]
    assert rows[0] == {
        "date": "20 Mar 2026",
        "description": "Newest",
        "category": "Bills",
        "amount": 300.0,
    }


def test_recent_transactions_respects_limit(client):
    assert len(get_recent_transactions(demo_id(), limit=3)) == 3


def test_recent_transactions_empty_user(client):
    assert get_recent_transactions(add_user()) == []


def test_category_breakdown_sorted_with_pct_summing_to_100(client):
    rows = get_category_breakdown(demo_id())
    assert len(rows) == 7
    amounts = [r["amount"] for r in rows]
    assert amounts == sorted(amounts, reverse=True)
    assert rows[0]["name"] == "Shopping"
    assert all(isinstance(r["pct"], int) for r in rows)
    assert sum(r["pct"] for r in rows) == 100


def test_category_breakdown_pct_absorbs_rounding_remainder(client):
    uid = add_user()
    add_expenses(
        uid,
        [(100, "Food", "2026-01-01", "a"), (100, "Bills", "2026-01-02", "b"),
         (100, "Other", "2026-01-03", "c")],
    )
    rows = get_category_breakdown(uid)
    assert sum(r["pct"] for r in rows) == 100


def test_category_breakdown_empty_user(client):
    assert get_category_breakdown(add_user()) == []


def test_queries_are_scoped_to_the_user(client):
    uid = add_user()
    add_expenses(uid, [(50, "Food", "2026-01-01", "Mine")])
    assert get_summary_stats(uid)["total_spent"] == 50.0
    assert [r["description"] for r in get_recent_transactions(uid)] == ["Mine"]
    assert [r["name"] for r in get_category_breakdown(uid)] == ["Food"]


# --------------------------------------------------------------- route tests

def test_profile_redirects_when_logged_out(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_shows_seed_user_data(client):
    login(client)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in html and DEMO_EMAIL in html
    assert "₹6,948.00" in html
    assert "Shopping" in html
    assert html.count("<tr>") - 1 == 8
    assert html.count('class="cat-row"') == 7
    assert "$" not in html


def test_profile_for_new_user_shows_empty_states(client):
    client.post(
        "/register",
        data={"name": "Asha Rao", "email": "asha@example.com", "password": "password123"},
    )
    client.post("/login", data={"email": "asha@example.com", "password": "password123"})
    html = client.get("/profile").get_data(as_text=True)
    assert "Asha Rao" in html
    assert "₹0.00" in html
    assert "No transactions yet." in html
    assert "Nothing to break down yet." in html


def test_profile_does_not_leak_other_users_expenses(client):
    other = add_user()
    add_expenses(other, [(99999, "Health", "2026-01-01", "SecretSurgery")])
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "SecretSurgery" not in html
    assert "₹6,948.00" in html


def test_profile_with_deleted_user_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
