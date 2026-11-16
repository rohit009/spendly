"""Tests for Step 7: add expense (GET/POST /expenses/add).

Written from .claude/specs/07-add-expense.md. "Today" and "tomorrow" are
computed with datetime.date so nothing depends on a hardcoded date.
"""
import re
from datetime import date, timedelta

import pytest

import database.db as db
from app import app as flask_app
from database.db import CATEGORIES
from database.queries import create_expense, get_summary_stats

URL = "/expenses/add"
TODAY = date.today()
TODAY_S = TODAY.isoformat()
TOMORROW_S = (TODAY + timedelta(days=1)).isoformat()
OLD_S = (TODAY - timedelta(days=30)).isoformat()


# ------------------------------------------------------------------ #
# Fixtures and helpers                                                #
# ------------------------------------------------------------------ #

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
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


def seed_expenses(user_id, rows):
    conn = db.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, *r) for r in rows],
    )
    conn.commit()
    conn.close()


def login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


@pytest.fixture
def uid(client):
    user_id = add_user()
    login(client, user_id)
    return user_id


def all_expenses():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM expenses ORDER BY id").fetchall()
    conn.close()
    return rows


def valid_form(**overrides):
    data = {
        "amount": "450.00",
        "category": "Food",
        "date": TODAY_S,
        "description": "Groceries",
    }
    data.update(overrides)
    return data


def post(client, **overrides):
    return client.post(URL, data=valid_form(**overrides))


def text(resp):
    return resp.get_data(as_text=True)


def assert_rejected(resp):
    """Form re-rendered (200), one inline alert, nothing saved."""
    assert resp.status_code == 200, "invalid input must re-render the form with 200"
    assert 'role="alert"' in text(resp), "expected an inline error block"
    assert all_expenses() == [], "invalid input must not insert a row"


# ------------------------------------------------------------------ #
# Auth guards                                                         #
# ------------------------------------------------------------------ #

def test_get_add_expense_logged_out_redirects_to_login(client):
    resp = client.get(URL)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_add_expense_logged_out_redirects_and_inserts_nothing(client):
    add_user()
    resp = client.post(URL, data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert all_expenses() == [], "logged-out POST must not insert"


# ------------------------------------------------------------------ #
# GET form                                                            #
# ------------------------------------------------------------------ #

class TestForm:
    def test_get_logged_in_returns_form_with_labelled_fields(self, client, uid):
        resp = client.get(URL)
        body = text(resp)
        assert resp.status_code == 200
        assert "<form" in body and 'method="post"' in body.lower()
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in body, f"missing field {field}"
            assert f'for="{field}"' in body or f"for='{field}'" in body, (
                f"missing <label> for {field}"
            )
        assert "Save expense" in body
        assert "Cancel" in body

    def test_category_dropdown_lists_exactly_the_seven_categories(self, client, uid):
        body = text(client.get(URL))
        values = re.findall(r'<option[^>]*value="([^"]*)"', body)
        assert [v for v in values if v] == CATEGORIES
        assert len(CATEGORIES) == 7
        assert "Choose a category" in body

    def test_date_field_defaults_to_today_and_max_is_today(self, client, uid):
        body = text(client.get(URL))
        assert f'value="{TODAY_S}"' in body, "date should default to today"
        assert f'max="{TODAY_S}"' in body, "date max should be today"

    def test_amount_and_description_attributes(self, client, uid):
        body = text(client.get(URL))
        assert 'step="0.01"' in body
        assert 'min="0.01"' in body
        assert 'maxlength="200"' in body
        assert "₹" in body

    def test_get_shows_no_error_block(self, client, uid):
        assert 'role="alert"' not in text(client.get(URL))

    def test_get_response_has_no_dollar_sign(self, client, uid):
        assert "$" not in text(client.get(URL))

    def test_profile_has_add_expense_button(self, client, uid):
        body = text(client.get("/profile"))
        assert f'href="{URL}"' in body, "profile must link to the add-expense form"
        assert "Add expense" in body


# ------------------------------------------------------------------ #
# Happy path                                                          #
# ------------------------------------------------------------------ #

class TestHappyPath:
    def test_valid_post_redirects_to_profile(self, client, uid):
        resp = post(client)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

    def test_valid_post_inserts_one_row_with_submitted_values(self, client, uid):
        post(client)
        rows = all_expenses()
        assert len(rows) == 1
        row = rows[0]
        assert row["user_id"] == uid
        assert row["amount"] == pytest.approx(450.0)
        assert row["category"] == "Food"
        assert row["date"] == TODAY_S
        assert row["description"] == "Groceries"

    def test_new_expense_appears_on_profile_with_rupee_format(self, client, uid):
        post(client, description="Groceries unique")
        body = text(client.get("/profile"))
        assert "Groceries unique" in body
        assert "₹450.00" in body
        assert "$" not in body

    def test_thousands_amount_uses_rupee_grouping(self, client, uid):
        post(client, amount="1850", description="Big shop")
        assert "₹1,850.00" in text(client.get("/profile"))

    def test_new_expense_is_first_in_transaction_history(self, client, uid):
        seed_expenses(uid, [(100.0, "Bills", OLD_S, "Older entry")])
        post(client, description="Newest entry")
        body = text(client.get("/profile"))
        assert body.index("Newest entry") < body.index("Older entry")

    def test_summary_stats_include_new_expense(self, client, uid):
        seed_expenses(uid, [
            (1000.0, "Food", OLD_S, "Old food"),
            (850.0, "Bills", OLD_S, "Old bill"),
        ])
        post(client, amount="450")
        stats = get_summary_stats(uid)
        assert stats["total_spent"] == pytest.approx(2300.0)
        assert stats["transaction_count"] == 3
        assert stats["top_category"] == "Food"

    @pytest.mark.parametrize("category", CATEGORIES)
    def test_every_category_is_accepted(self, client, uid, category):
        resp = post(client, category=category)
        assert resp.status_code == 302
        assert all_expenses()[0]["category"] == category

    @pytest.mark.parametrize(
        "raw, stored",
        [
            ("450", 450.0),
            ("450.5", 450.5),
            ("450.50", 450.5),
            ("0.01", 0.01),
            ("10000000", 10000000.0),
            ("10000000.00", 10000000.0),
        ],
    )
    def test_valid_amounts_are_accepted_and_stored(self, client, uid, raw, stored):
        resp = post(client, amount=raw)
        assert resp.status_code == 302, f"{raw} should be accepted"
        assert all_expenses()[0]["amount"] == pytest.approx(stored)

    def test_past_date_is_accepted(self, client, uid):
        assert post(client, date=OLD_S).status_code == 302
        assert all_expenses()[0]["date"] == OLD_S

    def test_refreshing_profile_after_save_does_not_duplicate(self, client, uid):
        resp = post(client)
        client.get(resp.headers["Location"])
        client.get(resp.headers["Location"])
        assert len(all_expenses()) == 1

    def test_sql_injection_in_description_is_stored_literally(self, client, uid):
        payload = "x'); DROP TABLE expenses;--"
        assert post(client, description=payload).status_code == 302
        rows = all_expenses()
        assert len(rows) == 1
        assert rows[0]["description"] == payload


# ------------------------------------------------------------------ #
# Description handling                                                #
# ------------------------------------------------------------------ #

class TestDescription:
    @pytest.mark.parametrize("blank", ["", "   ", "\t "])
    def test_blank_description_stored_as_null(self, client, uid, blank):
        resp = post(client, description=blank)
        assert resp.status_code == 302
        assert all_expenses()[0]["description"] is None

    def test_missing_description_field_is_accepted_as_null(self, client, uid):
        data = valid_form()
        del data["description"]
        assert client.post(URL, data=data).status_code == 302
        assert all_expenses()[0]["description"] is None

    def test_description_is_stripped(self, client, uid):
        post(client, description="   Lunch   ")
        assert all_expenses()[0]["description"] == "Lunch"

    def test_description_of_200_chars_is_accepted(self, client, uid):
        assert post(client, description="a" * 200).status_code == 302
        assert len(all_expenses()[0]["description"]) == 200

    def test_description_of_201_chars_is_rejected(self, client, uid):
        assert_rejected(post(client, description="a" * 201))


# ------------------------------------------------------------------ #
# Validation errors                                                   #
# ------------------------------------------------------------------ #

class TestValidation:
    @pytest.mark.parametrize(
        "bad_amount",
        ["abc", "0", "0.00", "-50", "12.345", "nan", "inf", "-inf", "",
         "   ", "10000000.01", "99999999"],
    )
    def test_invalid_amount_is_rejected(self, client, uid, bad_amount):
        assert_rejected(post(client, amount=bad_amount))

    def test_missing_amount_field_is_rejected(self, client, uid):
        data = valid_form()
        del data["amount"]
        assert_rejected(client.post(URL, data=data))

    @pytest.mark.parametrize(
        "bad_category",
        ["", "Groceries", "food", "FOOD", "Food'; DROP TABLE expenses;--", "Choose a category"],
    )
    def test_invalid_category_is_rejected(self, client, uid, bad_category):
        assert_rejected(post(client, category=bad_category))

    def test_missing_category_field_is_rejected(self, client, uid):
        data = valid_form()
        del data["category"]
        assert_rejected(client.post(URL, data=data))

    @pytest.mark.parametrize(
        "bad_date",
        ["", "garbage", "2026-1-5", "05-11-2026", "2026/11/05", "2026-13-01",
         "2026-02-30", "2025-02-29", TOMORROW_S, "9999-12-31"],
    )
    def test_invalid_or_future_date_is_rejected(self, client, uid, bad_date):
        assert_rejected(post(client, date=bad_date))

    def test_missing_date_field_is_rejected(self, client, uid):
        data = valid_form()
        del data["date"]
        assert_rejected(client.post(URL, data=data))

    def test_today_is_not_treated_as_future(self, client, uid):
        assert post(client, date=TODAY_S).status_code == 302

    def test_error_keeps_entered_values_in_form(self, client, uid):
        resp = post(client, amount="12.345", description="Kept note", date=OLD_S,
                    category="Health")
        body = text(resp)
        assert resp.status_code == 200
        assert "12.345" in body
        assert "Kept note" in body
        assert OLD_S in body
        assert re.search(r'<option[^>]*value="Health"[^>]*selected', body), (
            "chosen category should stay selected"
        )

    def test_error_response_shows_single_alert_and_no_dollar(self, client, uid):
        body = text(post(client, amount="abc"))
        assert body.count('role="alert"') == 1
        assert "$" not in body

    def test_multiple_invalid_fields_still_one_error_and_no_insert(self, client, uid):
        resp = post(client, amount="abc", category="Nope", date="bad")
        assert resp.status_code == 200
        assert text(resp).count('role="alert"') == 1
        assert all_expenses() == []


# ------------------------------------------------------------------ #
# Ownership / session                                                 #
# ------------------------------------------------------------------ #

class TestOwnership:
    def test_user_id_comes_from_session_not_form(self, client, uid):
        other = add_user("Ravi Kumar", "ravi@example.com")
        post(client, user_id=str(other))
        rows = all_expenses()
        assert len(rows) == 1
        assert rows[0]["user_id"] == uid, "user_id must be taken from the session"

    def test_other_user_does_not_see_new_expense(self, client, uid):
        other = add_user("Ravi Kumar", "ravi@example.com")
        post(client, description="Private groceries")
        login(client, other)
        body = text(client.get("/profile"))
        assert "Private groceries" not in body
        assert get_summary_stats(other)["transaction_count"] == 0

    def test_expenses_are_attributed_to_whichever_user_is_logged_in(self, client, uid):
        other = add_user("Ravi Kumar", "ravi@example.com")
        post(client, description="First")
        login(client, other)
        post(client, description="Second")
        owners = {r["description"]: r["user_id"] for r in all_expenses()}
        assert owners == {"First": uid, "Second": other}


# ------------------------------------------------------------------ #
# Date filter interaction                                             #
# ------------------------------------------------------------------ #

class TestDateFilter:
    def test_expense_inside_active_filter_is_shown(self, client, uid):
        post(client, date=TODAY_S, description="Inside filter")
        body = text(client.get(f"/profile?from={OLD_S}&to={TODAY_S}"))
        assert "Inside filter" in body

    def test_expense_outside_active_filter_is_hidden(self, client, uid):
        post(client, date=TODAY_S, description="Outside filter")
        far_from = "2020-01-01"
        far_to = "2020-01-31"
        body = text(client.get(f"/profile?from={far_from}&to={far_to}"))
        assert "Outside filter" not in body

    def test_filter_includes_only_matching_expense(self, client, uid):
        post(client, date=OLD_S, description="Old one")
        post(client, date=TODAY_S, description="Fresh one")
        body = text(client.get(f"/profile?from={TODAY_S}&to={TODAY_S}"))
        assert "Fresh one" in body
        assert "Old one" not in body


# ------------------------------------------------------------------ #
# create_expense query helper                                         #
# ------------------------------------------------------------------ #

class TestCreateExpenseHelper:
    def test_inserts_row_and_returns_new_id(self, client, uid):
        new_id = create_expense(uid, 450.0, "Food", TODAY_S, "Groceries")
        rows = all_expenses()
        assert len(rows) == 1
        assert new_id == rows[0]["id"]
        assert rows[0]["user_id"] == uid
        assert rows[0]["amount"] == pytest.approx(450.0)
        assert rows[0]["category"] == "Food"
        assert rows[0]["date"] == TODAY_S
        assert rows[0]["description"] == "Groceries"

    def test_second_insert_returns_different_id(self, client, uid):
        first = create_expense(uid, 100.0, "Bills", TODAY_S, None)
        second = create_expense(uid, 200.0, "Bills", TODAY_S, None)
        assert first != second
        assert len(all_expenses()) == 2

    def test_none_description_stored_as_null(self, client, uid):
        create_expense(uid, 100.0, "Other", TODAY_S, None)
        assert all_expenses()[0]["description"] is None

    def test_parameterised_insert_handles_quotes(self, client, uid):
        create_expense(uid, 100.0, "Other", TODAY_S, "it's '); DROP TABLE expenses;--")
        assert all_expenses()[0]["description"] == "it's '); DROP TABLE expenses;--"


# ------------------------------------------------------------------ #
# Session edge cases and nav                                          #
# ------------------------------------------------------------------ #

def test_stale_session_user_redirects_to_login_and_inserts_nothing(client):
    login(client, 9999)
    resp = post(client)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert all_expenses() == []


def test_decimal_amount_uses_rupee_grouping_on_profile(client, uid):
    post(client, amount="1850.50", category="Bills", description="Electricity bill")
    assert "₹1,850.50" in text(client.get("/profile"))


def test_navbar_links_to_add_expense_when_logged_in(client, uid):
    body = text(client.get("/profile"))
    assert body.count(f'href="{URL}"') >= 2, "navbar and profile button should both link"


def test_navbar_hides_add_expense_when_logged_out(client):
    assert f'href="{URL}"' not in text(client.get("/"))
