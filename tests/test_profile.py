import pathlib
import re

import pytest

import database.db as db
from app import app as flask_app, inr

ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def login(client):
    return client.post(
        "/login", data={"email": "demo@spendly.com", "password": "demo123"}
    )


def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_renders_when_logged_in(client):
    login(client)
    assert client.get("/profile").status_code == 200


def test_profile_shows_user_card_stats_table_and_breakdown(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)

    assert "Demo User" in html and "demo@spendly.com" in html
    assert html.count('class="stat-card"') >= 3
    assert "₹6,948.00" in html
    assert "Shopping" in html
    assert html.count("<tr>") - 1 >= 3  # minus the header row
    assert html.count('class="cat-row"') >= 3


def test_profile_uses_rupees_not_dollars(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "₹" in html
    assert "$" not in html


def test_profile_navbar_shows_signed_in_state(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "Sign out" in html
    assert "Get started" not in html


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, "₹0.00"),
        (999, "₹999.00"),
        (1000, "₹1,000.00"),
        (123456, "₹1,23,456.00"),
        (1234567.5, "₹12,34,567.50"),
        (-2500, "-₹2,500.00"),
    ],
)
def test_inr_filter_uses_indian_grouping(value, expected):
    assert inr(value) == expected


def test_profile_template_and_css_have_no_inline_styles_or_hex():
    template = (ROOT / "templates" / "profile.html").read_text()
    css = (ROOT / "static" / "css" / "profile.css").read_text()
    assert "style=" not in template
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", template)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_profile_template_handles_empty_data():
    from app import PROFILE_USER, _profile_summary

    stats, categories = _profile_summary([])
    with flask_app.test_request_context("/profile"):
        html = flask_app.jinja_env.get_template("profile.html").render(
            user=PROFILE_USER, stats=stats, transactions=[], categories=categories
        )
    assert "No transactions yet." in html
    assert "Nothing to break down yet." in html
    assert "₹0.00" in html
