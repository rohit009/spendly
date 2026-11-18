"""Tests for Step 8: edit expense (GET/POST /expenses/<id>/edit).

Written from .claude/specs/08-edit-expense.md. Dates are computed with
datetime.date so nothing depends on a hardcoded date.
"""

from datetime import date, timedelta

import pytest

import database.db as db
from app import app as flask_app
from database.queries import get_expense, get_recent_transactions, update_expense

TODAY_S = date.today().isoformat()
TOMORROW_S = (date.today() + timedelta(days=1)).isoformat()
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


def form(**overrides):
    data = {
        "amount": "1850.00",
        "category": "Bills",
        "date": TODAY_S,
        "description": "Electricity bill",
    }
    data.update(overrides)
    return data


def text(resp):
    return resp.get_data(as_text=True)


@pytest.fixture
def owned(client):
    """A logged-in user with one expense; returns (user_id, expense_id)."""
    uid = add_user()
    login(client, uid)
    return uid, add_expense_row(uid)


def url(eid):
    return f"/expenses/{eid}/edit"


# ------------------------------------------------------------------ #
# Auth and ownership                                                  #
# ------------------------------------------------------------------ #


def test_logged_out_get_and_post_redirect_to_login(client):
    eid = add_expense_row(add_user())
    before = all_expenses()
    for resp in (client.get(url(eid)), client.post(url(eid), data=form())):
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
    assert all_expenses() == before


def test_other_users_expense_is_404_and_unchanged(client):
    other = add_user("other@example.com")
    eid = add_expense_row(other)
    login(client, add_user("me@example.com"))
    before = all_expenses()
    assert client.get(url(eid)).status_code == 404
    assert client.post(url(eid), data=form()).status_code == 404
    assert all_expenses() == before


def test_missing_expense_is_404(client):
    login(client, add_user())
    assert client.get(url(9999)).status_code == 404
    assert client.post(url(9999), data=form()).status_code == 404


# ------------------------------------------------------------------ #
# GET                                                                 #
# ------------------------------------------------------------------ #


def test_get_prefills_form_in_edit_mode(client, owned):
    _, eid = owned
    body = text(client.get(url(eid)))
    assert 'value="450.00"' in body
    assert f'value="{OLD_S}"' in body
    assert 'value="Groceries"' in body
    assert '<option value="Food" selected>' in body
    assert f'action="{url(eid)}"' in body
    assert "Edit expense" in body
    assert "Save changes" in body
    assert "Add an expense" not in body


# ------------------------------------------------------------------ #
# POST success                                                        #
# ------------------------------------------------------------------ #


def test_post_updates_row_and_redirects(client, owned):
    uid, eid = owned
    created = all_expenses()[0]["created_at"]
    resp = client.post(url(eid), data=form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    rows = all_expenses()
    assert len(rows) == 1
    row = rows[0]
    assert (row["amount"], row["category"], row["date"], row["description"]) == (
        1850.0,
        "Bills",
        TODAY_S,
        "Electricity bill",
    )
    assert row["user_id"] == uid
    assert row["created_at"] == created


def test_blank_description_saved_as_null(client, owned):
    _, eid = owned
    client.post(url(eid), data=form(description="   "))
    assert all_expenses()[0]["description"] is None


def test_profile_shows_edited_amount_in_inr(client, owned):
    _, eid = owned
    client.post(url(eid), data=form(amount="123456"))
    body = text(client.get("/profile"))
    assert "₹1,23,456.00" in body
    assert "$" not in body


def test_profile_has_edit_link_per_row(client, owned):
    _, eid = owned
    assert f'href="{url(eid)}"' in text(client.get("/profile"))


# ------------------------------------------------------------------ #
# POST validation                                                     #
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": "0"},
        {"amount": "-50"},
        {"amount": "abc"},
        {"amount": "12.345"},
        {"amount": "nan"},
        {"amount": "inf"},
        {"amount": ""},
        {"amount": "10000001"},
        {"category": "Nonsense"},
        {"category": ""},
        {"date": ""},
        {"date": "2026-3-1"},
        {"date": "not-a-date"},
        {"date": TOMORROW_S},
        {"description": "x" * 201},
    ],
)
def test_invalid_input_rerenders_and_changes_nothing(client, owned, overrides):
    _, eid = owned
    before = all_expenses()
    resp = client.post(url(eid), data=form(**overrides))
    assert resp.status_code == 200
    assert 'role="alert"' in text(resp)
    assert all_expenses() == before


def test_typed_values_kept_on_error(client, owned):
    _, eid = owned
    body = text(client.post(url(eid), data=form(amount="abc", description="Kept")))
    assert 'value="abc"' in body or "abc" in body
    assert 'value="Kept"' in body


# ------------------------------------------------------------------ #
# Query helpers                                                       #
# ------------------------------------------------------------------ #


def test_get_expense_scoped_to_owner(client):
    a, b = add_user("a@example.com"), add_user("b@example.com")
    eid = add_expense_row(a)
    assert get_expense(a, eid)["description"] == "Groceries"
    assert get_expense(b, eid) is None
    assert get_expense(a, 9999) is None


def test_update_expense_scoped_to_owner(client):
    a, b = add_user("a@example.com"), add_user("b@example.com")
    eid = add_expense_row(a)
    assert update_expense(b, eid, 1.0, "Food", TODAY_S, "hack") is False
    assert all_expenses()[0]["amount"] == 450.0
    assert update_expense(a, eid, 99.5, "Other", TODAY_S, None) is True
    assert all_expenses()[0]["amount"] == 99.5


def test_recent_transactions_include_id(client):
    uid = add_user()
    eid = add_expense_row(uid)
    assert get_recent_transactions(uid)[0]["id"] == eid


def test_success_flashes_message_once(client, owned):
    _, eid = owned
    resp = client.post(url(eid), data=form(), follow_redirects=True)
    assert "Expense updated" in text(resp)
    assert "Expense updated" not in text(client.get("/profile"))


def test_failed_edit_does_not_flash(client, owned):
    _, eid = owned
    client.post(url(eid), data=form(amount="abc"))
    assert "Expense updated" not in text(client.get("/profile"))
