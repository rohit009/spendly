import os
import re
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

app = Flask(__name__)
# The fallback key is for local development only; set SECRET_KEY in production.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-key")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(error):
        return render_template("register.html", error=error, name=name, email=email)

    if not name:
        return fail("Please enter your name.")
    if "@" not in email or "." not in email.split("@", 1)[1]:
        return fail("Please enter a valid email address.")
    if len(password) < 8:
        return fail("Password must be at least 8 characters.")

    duplicate = "An account with this email already exists."
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return fail(duplicate)
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return fail(duplicate)
    finally:
        conn.close()

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    def fail(error):
        return render_template("login.html", error=error, email=email)

    if not email:
        return fail("Please enter your email address.")
    if not password:
        return fail("Please enter your password.")

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        return fail("Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.template_filter("inr")
def inr(value):
    """Format a number as rupees with Indian digit grouping, e.g. ₹1,23,456.00."""
    sign = "-" if value < 0 else ""
    whole, decimals = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}₹{whole}.{decimals}"


FILTER_ERROR = "Enter valid dates, with From on or before To."
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@app.template_filter("date_label")
def date_label(value):
    """Format an ISO date string (YYYY-MM-DD) as e.g. 01 Nov 2026."""
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")


def _parse_date(raw):
    """Return raw if it is a real zero-padded YYYY-MM-DD date, None if blank.

    Raises ValueError otherwise. strptime alone also accepts 2026-3-1, which
    would break the text comparison against stored ISO dates in SQL.
    """
    if not raw:
        return None
    if not ISO_DATE.fullmatch(raw):
        raise ValueError(raw)
    datetime.strptime(raw, "%Y-%m-%d")
    return raw


def _parse_range(raw_from, raw_to):
    """Validate the stripped ?from= / ?to= values (both optional).

    Returns (date_from, date_to, error). Anything invalid returns
    (None, None, FILTER_ERROR) so the page falls back to unfiltered data.
    """
    try:
        date_from, date_to = _parse_date(raw_from), _parse_date(raw_to)
    except ValueError:
        return None, None, FILTER_ERROR
    if date_from and date_to and date_from > date_to:
        return None, None, FILTER_ERROR
    return date_from, date_to, None


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        # The session points at a user that no longer exists.
        session.clear()
        return redirect(url_for("login"))

    # What the user typed is echoed back into the form, even when it is invalid.
    form_from = request.args.get("from", "").strip()
    form_to = request.args.get("to", "").strip()
    date_from, date_to, filter_error = _parse_range(form_from, form_to)

    return render_template(
        "profile.html",
        user=user,
        stats=get_summary_stats(user_id, date_from=date_from, date_to=date_to),
        transactions=get_recent_transactions(
            user_id, date_from=date_from, date_to=date_to
        ),
        categories=get_category_breakdown(
            user_id, date_from=date_from, date_to=date_to
        ),
        date_from=date_from,
        date_to=date_to,
        filter_active=bool(date_from or date_to),
        filter_error=filter_error,
        form_from=form_from,
        form_to=form_to,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
