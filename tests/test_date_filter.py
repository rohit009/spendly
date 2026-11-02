"""Tests for Step 6: date filter on the profile page.

All dates are explicit, so nothing here depends on today's date.
"""
import pytest

import database.db as db
from app import app as flask_app
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

# (amount, category, date, description)
EXPENSES = [
    (100.00, "Food", "2026-09-10", "Sep lunch"),
    (300.00, "Bills", "2026-10-05", "Oct bill"),
    (200.00, "Food", "2026-10-15", "Oct dinner"),
    (500.00, "Shopping", "2026-10-31", "Oct shoes"),
    (50.00, "Food", "2026-11-01", "Nov snack"),
    (150.00, "Transport", "2026-11-02", "Nov cab"),
]
OCT = ("2026-10-01", "2026-10-31")


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


def add_expenses(user_id, rows):
    conn = db.get_db()
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, *r) for r in rows],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def uid(client):
    user_id = add_user()
    add_expenses(user_id, EXPENSES)
    return user_id


def login(client, user_id):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id


def profile(client, query=""):
    return client.get("/profile" + query)


# ------------------------------------------------------------------ #
# Unit tests                                                          #
# ------------------------------------------------------------------ #

def test_stats_partial_range(uid):
    stats = get_summary_stats(uid, *OCT)
    assert stats == {"total_spent": 1000.0, "transaction_count": 3, "top_category": "Shopping"}


def test_stats_empty_range(uid):
    stats = get_summary_stats(uid, "2025-01-01", "2025-01-31")
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_stats_no_dates_equals_all(uid):
    assert get_summary_stats(uid)["total_spent"] == 1300.0
    assert get_summary_stats(uid)["transaction_count"] == 6


def test_transactions_date_from_only(uid):
    rows = get_recent_transactions(uid, date_from="2026-10-31")
    assert [r["description"] for r in rows] == ["Nov cab", "Nov snack", "Oct shoes"]


def test_transactions_date_to_only(uid):
    rows = get_recent_transactions(uid, date_to="2026-10-05")
    assert [r["description"] for r in rows] == ["Oct bill", "Sep lunch"]


def test_transactions_single_day_is_inclusive(uid):
    rows = get_recent_transactions(uid, date_from="2026-10-15", date_to="2026-10-15")
    assert [r["description"] for r in rows] == ["Oct dinner"]


def test_transactions_range_newest_first(uid):
    rows = get_recent_transactions(uid, date_from=OCT[0], date_to=OCT[1])
    assert [r["description"] for r in rows] == ["Oct shoes", "Oct dinner", "Oct bill"]


def test_transactions_limit_applies_after_filter(uid):
    rows = get_recent_transactions(uid, limit=2, date_from=OCT[0], date_to=OCT[1])
    assert [r["description"] for r in rows] == ["Oct shoes", "Oct dinner"]


def test_breakdown_filtered_range(uid):
    cats = get_category_breakdown(uid, *OCT)
    assert [(c["name"], c["amount"], c["pct"]) for c in cats] == [
        ("Shopping", 500.0, 50),
        ("Bills", 300.0, 30),
        ("Food", 200.0, 20),
    ]
    assert sum(c["pct"] for c in cats) == 100


def test_breakdown_pct_sums_to_100_for_awkward_split(client):
    user_id = add_user("Thirds", "thirds@example.com")
    add_expenses(user_id, [(100, "Food", "2026-10-01", ""),
                           (100, "Bills", "2026-10-02", ""),
                           (100, "Other", "2026-10-03", "")])
    cats = get_category_breakdown(user_id, "2026-10-01", "2026-10-31")
    assert sum(c["pct"] for c in cats) == 100


def test_breakdown_empty_range(uid):
    assert get_category_breakdown(uid, "2025-01-01", "2025-01-31") == []


def test_no_dates_matches_unfiltered(uid):
    assert get_category_breakdown(uid, None, None) == get_category_breakdown(uid)
    assert get_recent_transactions(uid, date_from=None, date_to=None) == get_recent_transactions(uid)


def test_other_users_expenses_never_included(client, uid):
    other = add_user("Other Person", "other@example.com")
    add_expenses(other, [(9999.0, "Bills", "2026-10-10", "Not yours")])
    assert get_summary_stats(uid, *OCT)["total_spent"] == 1000.0
    assert all(r["description"] != "Not yours" for r in get_recent_transactions(uid, date_from=OCT[0], date_to=OCT[1]))
    assert all(c["amount"] < 9999 for c in get_category_breakdown(uid, *OCT))


# ------------------------------------------------------------------ #
# Route tests                                                         #
# ------------------------------------------------------------------ #

def test_logged_out_redirects_to_login(client):
    resp = profile(client, "?from=2026-10-01&to=2026-10-31")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_valid_range_filters_everything(client, uid):
    login(client, uid)
    resp = profile(client, "?from=2026-10-01&to=2026-10-31")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹1,000.00" in html
    assert "Oct shoes" in html and "Oct bill" in html
    assert "Sep lunch" not in html and "Nov cab" not in html
    assert html.count('class="cat-row"') == 3
    assert "$" not in html


def test_only_from(client, uid):
    login(client, uid)
    html = profile(client, "?from=2026-10-31").get_data(as_text=True)
    assert "₹700.00" in html
    assert "Nov cab" in html and "Oct shoes" in html and "Oct dinner" not in html


def test_only_to(client, uid):
    login(client, uid)
    html = profile(client, "?to=2026-10-05").get_data(as_text=True)
    assert "₹400.00" in html
    assert "Sep lunch" in html and "Oct bill" in html and "Oct dinner" not in html


def test_boundary_dates_are_included(client, uid):
    login(client, uid)
    html = profile(client, "?from=2026-10-05&to=2026-10-31").get_data(as_text=True)
    assert "Oct bill" in html and "Oct shoes" in html


def test_empty_range_shows_zeroes_and_messages(client, uid):
    login(client, uid)
    resp = profile(client, "?from=2025-01-01&to=2025-01-31")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "₹0.00" in html
    assert "No transactions in this date range." in html
    assert "Nothing to break down in this date range." in html


def test_form_is_prefilled(client, uid):
    login(client, uid)
    html = profile(client, "?from=2026-10-01&to=2026-10-31").get_data(as_text=True)
    assert 'value="2026-10-01"' in html
    assert 'value="2026-10-31"' in html


def test_no_filter_matches_step_5(client, uid):
    login(client, uid)
    html = profile(client).get_data(as_text=True)
    assert "₹1,300.00" in html
    assert "Showing" not in html
    assert "Enter valid dates" not in html


@pytest.mark.parametrize("query", [
    "?from=2026-10-31&to=2026-10-01",   # reversed
    "?from=abc",
    "?to=2026-13-45",
    "?from=2026-02-30",
    "?from=%27%20OR%201%3D1%20--",     # ' OR 1=1 --
])
def test_invalid_input_shows_error_and_unfiltered_data(client, uid, query):
    login(client, uid)
    resp = profile(client, query)
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Enter valid dates, with From on or before To." in html
    assert "₹1,300.00" in html  # unfiltered


def test_blank_values_are_no_filter(client, uid):
    login(client, uid)
    resp = profile(client, "?from=&to=")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Enter valid dates" not in html
    assert "₹1,300.00" in html


def test_filter_does_not_leak_other_users(client, uid):
    other = add_user("Other Person", "other@example.com")
    add_expenses(other, [(9999.0, "Bills", "2026-10-10", "Not yours")])
    login(client, uid)
    html = profile(client, "?from=2026-10-01&to=2026-10-31").get_data(as_text=True)
    assert "Not yours" not in html
    assert "₹1,000.00" in html


def test_unpadded_date_is_invalid(client, uid):
    login(client, uid)
    html = profile(client, "?from=2026-3-1").get_data(as_text=True)
    assert "Enter valid dates, with From on or before To." in html
    assert "₹1,300.00" in html


def test_error_is_above_the_form(client, uid):
    login(client, uid)
    html = profile(client, "?from=abc").get_data(as_text=True)
    assert html.index("Enter valid dates") < html.index('class="filter-form"')


@pytest.mark.parametrize("query, note", [
    ("?from=2026-10-01&to=2026-10-31", "Showing 01 Oct 2026 to 31 Oct 2026"),
    ("?from=2026-10-31", "Showing 31 Oct 2026 onwards"),
    ("?to=2026-10-05", "Showing up to 05 Oct 2026"),
])
def test_filter_note_wording(client, uid, query, note):
    login(client, uid)
    html = profile(client, query).get_data(as_text=True)
    assert note in html
