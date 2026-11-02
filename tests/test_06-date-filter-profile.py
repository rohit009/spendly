"""Tests for Step 6: Date Filter for Profile Page.

Written from .claude/specs/06-date-filter-profile.md only. All dates are
explicit, so nothing depends on today's date.
"""
import re

import pytest

import database.db as db
from app import app as flask_app
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

ERROR_MSG = "Enter valid dates, with From on or before To."
EMPTY_TXN_FILTERED = "No transactions in this date range."
EMPTY_CAT_FILTERED = "Nothing to break down in this date range."
EMPTY_TXN_PLAIN = "No transactions yet."
EMPTY_CAT_PLAIN = "Nothing to break down yet."

# (amount, category, date, description) for the main user, spanning 5 months.
MAIN_ROWS = [
    (100, "Food", "2026-01-10", "JanFood"),
    (200, "Bills", "2026-02-15", "FebBills"),
    (300, "Food", "2026-03-01", "MarFirst"),
    (400, "Travel", "2026-03-15", "MarMid"),
    (500, "Food", "2026-03-31", "MarLast"),
    (1000, "Shopping", "2026-04-10", "AprShop"),
    (123456, "Health", "2026-05-05", "MayBig"),
]
ALL_DESCRIPTIONS = [r[3] for r in MAIN_ROWS]
MARCH_DESCRIPTIONS = ["MarFirst", "MarMid", "MarLast"]
OTHER_USER_DESC = "OtherUserSecret"


# ------------------------------------------------------------------ helpers

def add_user(name, email):
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


def count_expenses():
    conn = db.get_db()
    n = conn.execute("SELECT COUNT(*) AS n FROM expenses").fetchone()["n"]
    conn.close()
    return n


def login_as(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def page(client, query=""):
    resp = client.get("/profile" + query)
    return resp, resp.get_data(as_text=True)


def assert_only(html, present, all_names=ALL_DESCRIPTIONS):
    for name in all_names:
        if name in present:
            assert name in html, f"{name} should be shown"
        else:
            assert name not in html, f"{name} should NOT be shown"


# ----------------------------------------------------------------- fixtures

@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.config["TESTING"] = True
    uid = add_user("Main User", "main@example.com")
    other = add_user("Other User", "other@example.com")
    add_expenses(uid, MAIN_ROWS)
    # Other user's expenses sit inside every range used below.
    add_expenses(
        other,
        [
            (77777, "Health", "2026-03-10", OTHER_USER_DESC),
            (55555, "Food", "2026-01-10", OTHER_USER_DESC),
            (44444, "Bills", "2026-05-05", OTHER_USER_DESC),
        ],
    )
    return {"uid": uid, "other": other, "client": flask_app.test_client()}


@pytest.fixture
def uid(env):
    return env["uid"]


@pytest.fixture
def client(env):
    c = env["client"]
    login_as(c, env["uid"])
    return c


# --------------------------------------------------------------- unit tests

class TestSummaryStats:
    def test_partial_range_uses_only_that_range(self, uid):
        stats = get_summary_stats(uid, date_from="2026-03-01", date_to="2026-03-31")
        assert stats["total_spent"] == 1200, stats
        assert stats["transaction_count"] == 3, stats
        assert stats["top_category"] == "Food", stats

    def test_top_category_comes_from_filtered_range(self, uid):
        stats = get_summary_stats(uid, date_from="2026-04-01", date_to="2026-05-31")
        assert stats["top_category"] == "Health", stats
        assert stats["transaction_count"] == 2

    def test_empty_range_returns_zeros(self, uid):
        stats = get_summary_stats(uid, date_from="2027-01-01", date_to="2027-01-31")
        assert stats == {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—",
        }

    def test_only_date_from(self, uid):
        stats = get_summary_stats(uid, date_from="2026-04-10")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == 124456

    def test_only_date_to(self, uid):
        stats = get_summary_stats(uid, date_to="2026-02-15")
        assert stats["transaction_count"] == 2
        assert stats["total_spent"] == 300

    def test_single_day_range_is_inclusive(self, uid):
        stats = get_summary_stats(uid, date_from="2026-03-15", date_to="2026-03-15")
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == 400
        assert stats["top_category"] == "Travel"

    def test_no_arguments_covers_everything(self, uid):
        stats = get_summary_stats(uid)
        assert stats["total_spent"] == 125956
        assert stats["transaction_count"] == 7

    def test_other_users_expenses_never_included(self, uid):
        stats = get_summary_stats(uid, date_from="2026-03-01", date_to="2026-03-31")
        assert stats["total_spent"] == 1200, "other user's 77777 must not be added"


class TestRecentTransactions:
    def test_date_from_only_newest_first(self, uid):
        rows = get_recent_transactions(uid, date_from="2026-03-01")
        assert [r["description"] for r in rows] == [
            "MayBig", "AprShop", "MarLast", "MarMid", "MarFirst",
        ]

    def test_date_to_only(self, uid):
        rows = get_recent_transactions(uid, date_to="2026-03-01")
        assert [r["description"] for r in rows] == ["MarFirst", "FebBills", "JanFood"]

    def test_same_day_range_returns_only_that_day(self, uid):
        rows = get_recent_transactions(
            uid, date_from="2026-03-31", date_to="2026-03-31"
        )
        assert [r["description"] for r in rows] == ["MarLast"]

    def test_both_boundaries_inclusive(self, uid):
        rows = get_recent_transactions(
            uid, date_from="2026-03-01", date_to="2026-03-31"
        )
        assert sorted(r["description"] for r in rows) == sorted(MARCH_DESCRIPTIONS)

    def test_empty_range_returns_empty_list(self, uid):
        assert get_recent_transactions(
            uid, date_from="2027-01-01", date_to="2027-01-31"
        ) == []

    def test_limit_applies_after_filtering(self, env):
        new_uid = add_user("Busy", "busy@example.com")
        # 12 rows in March, 5 rows in June (newer, outside the range).
        add_expenses(
            new_uid,
            [(10, "Food", f"2026-03-{d:02d}", f"M{d:02d}") for d in range(1, 13)]
            + [(10, "Food", f"2026-06-{d:02d}", f"J{d:02d}") for d in range(1, 6)],
        )
        rows = get_recent_transactions(
            new_uid, limit=10, date_from="2026-03-01", date_to="2026-03-31"
        )
        assert len(rows) == 10, "limit of 10 should apply to filtered rows"
        assert all(r["description"].startswith("M") for r in rows)
        assert rows[0]["description"] == "M12", "newest first"

    def test_no_arguments_returns_all_newest_first(self, uid):
        rows = get_recent_transactions(uid)
        assert [r["description"] for r in rows] == [
            "MayBig", "AprShop", "MarLast", "MarMid", "MarFirst", "FebBills", "JanFood",
        ]

    def test_other_users_rows_never_included(self, uid):
        rows = get_recent_transactions(
            uid, date_from="2026-01-01", date_to="2026-12-31"
        )
        assert OTHER_USER_DESC not in [r["description"] for r in rows]
        assert len(rows) == 7


class TestCategoryBreakdown:
    def test_filtered_amounts_only_from_range(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-03-01", date_to="2026-03-31")
        amounts = {r["name"]: r["amount"] for r in rows}
        assert amounts == {"Food": 800, "Travel": 400}

    def test_filtered_pct_sums_to_100(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-03-01", date_to="2026-03-31")
        assert sum(r["pct"] for r in rows) == 100, rows

    def test_pct_based_on_filtered_total(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-03-01", date_to="2026-03-31")
        pct = {r["name"]: r["pct"] for r in rows}
        assert pct["Food"] == 67 and pct["Travel"] == 33, pct

    def test_pct_sums_to_100_for_awkward_split(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-01-01", date_to="2026-03-15")
        assert sum(r["pct"] for r in rows) == 100, rows

    def test_sorted_by_amount_descending(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-03-01", date_to="2026-05-31")
        amounts = [r["amount"] for r in rows]
        assert amounts == sorted(amounts, reverse=True)

    def test_empty_range_returns_empty_list(self, uid):
        assert get_category_breakdown(
            uid, date_from="2027-01-01", date_to="2027-01-31"
        ) == []

    def test_only_date_from(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-05-01")
        assert [r["name"] for r in rows] == ["Health"]
        assert rows[0]["pct"] == 100

    def test_only_date_to(self, uid):
        rows = get_category_breakdown(uid, date_to="2026-02-28")
        assert {r["name"] for r in rows} == {"Food", "Bills"}
        assert sum(r["pct"] for r in rows) == 100

    def test_no_arguments_covers_everything(self, uid):
        rows = get_category_breakdown(uid)
        assert {r["name"] for r in rows} == {
            "Food", "Bills", "Travel", "Shopping", "Health",
        }
        assert sum(r["amount"] for r in rows) == 125956
        assert sum(r["pct"] for r in rows) == 100

    def test_other_users_expenses_never_included(self, uid):
        rows = get_category_breakdown(uid, date_from="2026-03-01", date_to="2026-03-31")
        assert "Health" not in {r["name"] for r in rows}


def test_helpers_accept_keyword_dates_and_match_unfiltered_when_none(uid):
    assert get_summary_stats(uid, date_from=None, date_to=None) == get_summary_stats(uid)
    assert get_recent_transactions(
        uid, date_from=None, date_to=None
    ) == get_recent_transactions(uid)
    assert get_category_breakdown(
        uid, date_from=None, date_to=None
    ) == get_category_breakdown(uid)


# --------------------------------------------------------------- route tests

class TestAuthGuard:
    def test_logged_out_redirects_to_login(self, env):
        resp = env["client"].get("/profile?from=2026-03-01&to=2026-03-31")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login") or "/login" in resp.headers["Location"]

    def test_filter_params_not_preserved_in_redirect(self, env):
        resp = env["client"].get("/profile?from=2026-03-01&to=2026-03-31")
        location = resp.headers["Location"]
        assert "from=" not in location and "to=" not in location, location


class TestFilteredProfile:
    def test_valid_range_filters_all_three_sections(self, client):
        resp, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert resp.status_code == 200
        assert_only(html, MARCH_DESCRIPTIONS)
        assert "₹1,200.00" in html, "total spent for March"
        assert html.count('class="cat-row"') == 2, "Food and Travel only"
        assert ERROR_MSG not in html

    def test_only_from_is_filtered(self, client):
        resp, html = page(client, "?from=2026-04-10")
        assert resp.status_code == 200
        assert_only(html, ["AprShop", "MayBig"])
        assert ERROR_MSG not in html

    def test_only_to_is_filtered(self, client):
        resp, html = page(client, "?to=2026-02-15")
        assert resp.status_code == 200
        assert_only(html, ["JanFood", "FebBills"])
        assert ERROR_MSG not in html

    def test_boundary_dates_are_included(self, client):
        resp, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert "MarFirst" in html, "From date is inclusive"
        assert "MarLast" in html, "To date is inclusive"

    def test_single_day_range(self, client):
        resp, html = page(client, "?from=2026-03-15&to=2026-03-15")
        assert resp.status_code == 200
        assert_only(html, ["MarMid"])
        assert "₹400.00" in html
        assert ERROR_MSG not in html

    def test_other_users_data_never_shown_in_range(self, client):
        for query in ("?from=2026-03-01&to=2026-03-31", "?from=2026-01-01", "?to=2026-12-31"):
            resp, html = page(client, query)
            assert OTHER_USER_DESC not in html, query
            assert "77,777" not in html, query

    def test_empty_range_shows_zero_and_filtered_empty_states(self, client):
        resp, html = page(client, "?from=2027-01-01&to=2027-01-31")
        assert resp.status_code == 200
        assert "₹0.00" in html
        assert EMPTY_TXN_FILTERED in html
        assert EMPTY_CAT_FILTERED in html
        assert ERROR_MSG not in html
        assert_only(html, [])
        assert html.count('class="cat-row"') == 0

    def test_empty_range_does_not_show_unfiltered_empty_messages(self, client):
        _, html = page(client, "?from=2027-01-01&to=2027-01-31")
        assert EMPTY_TXN_PLAIN not in html
        assert EMPTY_CAT_PLAIN not in html

    def test_inputs_prefilled_with_submitted_dates(self, client):
        resp, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert 'name="from"' in html and 'name="to"' in html
        assert 'type="date"' in html
        assert "2026-03-01" in html and "2026-03-31" in html
        assert 'value="2026-03-01"' in html
        assert 'value="2026-03-31"' in html

    def test_only_from_prefills_only_from(self, client):
        _, html = page(client, "?from=2026-04-10")
        assert 'value="2026-04-10"' in html

    def test_active_filter_summary_line(self, client):
        _, html = page(client, "?from=2026-03-01&to=2026-03-31")
        note = re.search(r'<p class="filter-note">(.*?)</p>', html, re.S)
        assert note, "filter note missing"
        assert "01 Mar 2026" in note.group(1)
        assert "31 Mar 2026" in note.group(1)

    def test_filter_form_has_apply_and_clear(self, client):
        _, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert "Apply" in html
        assert "Clear" in html
        assert "<label" in html
        assert 'method="get"' in html.lower()

    def test_inr_with_indian_grouping_and_no_dollar(self, client):
        resp, html = page(client, "?from=2026-05-01&to=2026-05-31")
        assert "₹1,23,456.00" in html, "Indian digit grouping expected"
        assert "$" not in html

    @pytest.mark.parametrize(
        "query",
        [
            "",
            "?from=2026-03-01&to=2026-03-31",
            "?from=2027-01-01&to=2027-01-31",
            "?from=abc",
            "?from=2026-04-01&to=2026-03-01",
        ],
    )
    def test_no_dollar_sign_anywhere(self, client, query):
        resp, html = page(client, query)
        assert resp.status_code == 200
        assert "$" not in html, query

    def test_categories_percent_in_page_sum_to_100(self, client):
        # Verified through the helper that feeds the same range as the page.
        _, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert "67%" in html and "33%" in html


class TestNoFilter:
    def test_no_params_shows_everything(self, client):
        resp, html = page(client)
        assert resp.status_code == 200
        assert_only(html, ALL_DESCRIPTIONS)
        assert "₹1,25,956.00" in html
        assert html.count('class="cat-row"') == 5
        assert ERROR_MSG not in html
        assert OTHER_USER_DESC not in html

    def test_blank_values_treated_as_no_filter(self, client):
        resp, html = page(client, "?from=&to=")
        assert resp.status_code == 200
        assert_only(html, ALL_DESCRIPTIONS)
        assert ERROR_MSG not in html
        assert EMPTY_TXN_FILTERED not in html

    def test_blank_from_with_valid_to_is_open_ended(self, client):
        resp, html = page(client, "?from=&to=2026-02-15")
        assert resp.status_code == 200
        assert_only(html, ["JanFood", "FebBills"])
        assert ERROR_MSG not in html

    def test_blank_to_with_valid_from_is_open_ended(self, client):
        resp, html = page(client, "?from=2026-05-01&to=")
        assert resp.status_code == 200
        assert_only(html, ["MayBig"])
        assert ERROR_MSG not in html

    def test_new_user_without_filter_sees_plain_empty_states(self, env):
        fresh = add_user("Fresh", "fresh@example.com")
        c = env["client"]
        login_as(c, fresh)
        _, html = page(c)
        assert EMPTY_TXN_PLAIN in html
        assert EMPTY_CAT_PLAIN in html
        assert EMPTY_TXN_FILTERED not in html


class TestInvalidInput:
    @pytest.mark.parametrize(
        "query",
        [
            "?from=2026-04-01&to=2026-03-01",  # From after To
            "?from=abc",
            "?to=abc",
            "?from=abc&to=2026-13-45",
            "?to=2026-13-45",
            "?from=2026-02-30",  # impossible date
            "?to=2026-02-30",
            "?from=2026-02-30&to=2026-03-31",
            "?from=03/01/2026",  # wrong format
            "?from=2026-3-1",
            "?from=%27%20OR%201%3D1%20--",  # ' OR 1=1 --
            "?to=%27%20OR%201%3D1%20--",
            "?from=2026-03-01%27%3B%20DROP%20TABLE%20expenses%3B--",
        ],
    )
    def test_bad_input_shows_error_and_unfiltered_data(self, client, query):
        resp, html = page(client, query)
        assert resp.status_code == 200, f"{query} must not 400/500"
        assert ERROR_MSG in html, f"error message expected for {query}"
        assert_only(html, ALL_DESCRIPTIONS)
        assert "₹1,25,956.00" in html, "unfiltered total expected"
        assert OTHER_USER_DESC not in html

    def test_error_not_shown_for_valid_range(self, client):
        _, html = page(client, "?from=2026-03-01&to=2026-03-31")
        assert ERROR_MSG not in html

    def test_from_equal_to_is_valid(self, client):
        resp, html = page(client, "?from=2026-03-15&to=2026-03-15")
        assert ERROR_MSG not in html

    def test_error_message_appears_once(self, client):
        _, html = page(client, "?from=2026-04-01&to=2026-03-01")
        assert html.count(ERROR_MSG) == 1

    def test_injection_value_is_not_reflected_unescaped(self, client):
        _, html = page(client, "?from=%27%20OR%201%3D1%20--")
        assert "' OR 1=1 --" not in html

    def test_injection_does_not_alter_data(self, env, client):
        before = count_expenses()
        page(client, "?from=2026-03-01%27%3B%20DROP%20TABLE%20expenses%3B--")
        page(client, "?to=%27%20OR%201%3D1%20--")
        assert count_expenses() == before, "expenses table must be untouched"

    def test_injection_does_not_widen_to_other_users(self, client):
        _, html = page(client, "?from=%27%20OR%201%3D1%20--")
        assert OTHER_USER_DESC not in html
        assert "77,777" not in html

    def test_error_state_has_no_filter_active_messages(self, client):
        _, html = page(client, "?from=2026-04-01&to=2026-03-01")
        assert EMPTY_TXN_FILTERED not in html
        assert EMPTY_CAT_FILTERED not in html


def test_existing_session_for_other_user_sees_only_their_rows(env):
    c = env["client"]
    login_as(c, env["other"])
    resp, html = page(c, "?from=2026-03-01&to=2026-03-31")
    assert resp.status_code == 200
    assert OTHER_USER_DESC in html
    assert_only(html, [])
    assert "₹77,777.00" in html
