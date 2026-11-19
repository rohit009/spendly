"""Tests for Step 9: delete expense (GET/POST /expenses/<id>/delete).

Written from .claude/specs/09-delete-expense.md.
"""

from datetime import date, timedelta

import pytest

import database.db as db
from app import app as flask_app
from database.queries import (
    delete_expense_row,
    get_category_breakdown,
    get_summary_stats,
)

TODAY_S = date.today().isoformat()
OLD_S = (date.today() - timedelta(days=30)).isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def add_user(email="asha@example.com"):
    conn = db.get_db()
    cur = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Asha Rao", email, "x"),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def add_expense_row(
    user_id, amount=450.0, category="Food", day=OLD_S, description="Groceries"
):
    conn = db.get_db()
    cur = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, day, description),
    )
    conn.commit()
    eid = cur.lastrowid
    conn.close()
    return eid


def login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def all_expenses():
    conn = db.get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM expenses ORDER BY id")]
    conn.close()
    return rows


def text(resp):
    return resp.get_data(as_text=True)


def url(eid):
    return f"/expenses/{eid}/delete"


@pytest.fixture
def owned(client):
    """A logged-in user with one expense; returns (user_id, expense_id)."""
    uid = add_user()
    login(client, uid)
    return uid, add_expense_row(uid)


# ------------------------------------------------------------------ #
# Auth and ownership                                                  #
# ------------------------------------------------------------------ #


def test_logged_out_get_and_post_redirect_to_login(client):
    eid = add_expense_row(add_user())
    before = all_expenses()
    for resp in (client.get(url(eid)), client.post(url(eid))):
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
    assert all_expenses() == before


def test_other_users_expense_is_404_and_kept(client):
    eid = add_expense_row(add_user("other@example.com"))
    login(client, add_user("me@example.com"))
    before = all_expenses()
    assert client.get(url(eid)).status_code == 404
    assert client.post(url(eid)).status_code == 404
    assert all_expenses() == before


def test_missing_expense_is_404(client):
    login(client, add_user())
    assert client.get(url(9999)).status_code == 404
    assert client.post(url(9999)).status_code == 404


# ------------------------------------------------------------------ #
# GET confirmation page                                               #
# ------------------------------------------------------------------ #


def test_get_shows_summary_and_deletes_nothing(client):
    uid = add_user()
    login(client, uid)
    eid = add_expense_row(uid, amount=123456, category="Bills", day="2026-03-20",
                          description="Rent")
    before = all_expenses()
    for _ in range(2):  # refreshing is harmless
        resp = client.get(url(eid))
        body = text(resp)
        assert resp.status_code == 200
        assert "Delete expense?" in body
        assert "₹1,23,456.00" in body
        assert "Bills" in body and "20 Mar 2026" in body and "Rent" in body
        assert "$" not in body
        assert f'action="{url(eid)}"' in body
        assert 'href="/profile"' in body  # Cancel
    assert all_expenses() == before


def test_get_blank_description_shows_dash(client):
    uid = add_user()
    login(client, uid)
    eid = add_expense_row(uid, description=None)
    assert "—" in text(client.get(url(eid)))


# ------------------------------------------------------------------ #
# POST                                                                #
# ------------------------------------------------------------------ #


def test_post_deletes_only_target_and_redirects(client):
    uid = add_user()
    other = add_user("other@example.com")
    login(client, uid)
    target = add_expense_row(uid, description="Target")
    keep = add_expense_row(uid, description="Keep")
    other_row = add_expense_row(other, description="Theirs")
    resp = client.post(url(target))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert [r["id"] for r in all_expenses()] == [keep, other_row]


def test_flash_shown_once(client, owned):
    _, eid = owned
    resp = client.post(url(eid), follow_redirects=True)
    assert "Expense deleted" in text(resp)
    assert "Expense deleted" not in text(client.get("/profile"))


def test_second_post_is_404_without_flash(client, owned):
    _, eid = owned
    client.post(url(eid))
    assert client.post(url(eid)).status_code == 404
    client.get("/profile")  # consume the first (legitimate) flash
    assert "Expense deleted" not in text(client.get("/profile"))


# ------------------------------------------------------------------ #
# Effects on profile                                                  #
# ------------------------------------------------------------------ #


def test_profile_has_delete_link_with_label(client, owned):
    _, eid = owned
    body = text(client.get("/profile"))
    assert f'href="{url(eid)}"' in body
    assert 'aria-label="Delete expense: Groceries"' in body


def test_stats_and_breakdown_drop_deleted_amount(client):
    uid = add_user()
    login(client, uid)
    keep = add_expense_row(uid, amount=200, category="Food")
    gone = add_expense_row(uid, amount=800, category="Bills")
    assert get_summary_stats(uid)["total_spent"] == 1000.0
    client.post(url(gone))
    assert get_summary_stats(uid)["total_spent"] == 200.0
    assert [r["name"] for r in get_category_breakdown(uid)] == ["Food"]
    assert keep


def test_deleting_last_expense_shows_empty_state(client, owned):
    _, eid = owned
    body = text(client.post(url(eid), follow_redirects=True))
    assert "No transactions yet." in body


def test_delete_inside_date_filter_updates_filtered_view(client):
    uid = add_user()
    login(client, uid)
    inside = add_expense_row(uid, day=TODAY_S, description="InRange")
    add_expense_row(uid, day=OLD_S, description="OutRange")
    query = f"/profile?from={TODAY_S}&to={TODAY_S}"
    assert "InRange" in text(client.get(query))
    client.post(url(inside))
    body = text(client.get(query))
    assert "InRange" not in body
    assert "No transactions in this date range." in body


def test_edit_flow_still_works(client, owned):
    _, eid = owned
    assert client.get(f"/expenses/{eid}/edit").status_code == 200


# ------------------------------------------------------------------ #
# Query helper                                                        #
# ------------------------------------------------------------------ #


def test_delete_expense_row_scoped_to_owner(client):
    a, b = add_user("a@example.com"), add_user("b@example.com")
    eid = add_expense_row(a)
    assert delete_expense_row(b, eid) is False
    assert len(all_expenses()) == 1
    assert delete_expense_row(a, 9999) is False
    assert delete_expense_row(a, eid) is True
    assert all_expenses() == []
