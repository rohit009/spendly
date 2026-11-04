import os
import re
import secrets
import sqlite3
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import CATEGORIES, get_db, init_db, seed_db
from database.queries import (
    create_expense,
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

MAX_AMOUNT = Decimal("10000000")  # ₹1,00,00,000
MAX_DESCRIPTION = 200
AMOUNT_FORMAT_ERROR = "Enter an amount in rupees, e.g. 450 or 450.50."

app = Flask(__name__)
# Set SECRET_KEY in production. Without it a random key is generated on every
# start, so sessions do not survive a restart, but the key is never guessable.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
# Lax stops browsers sending the session cookie on cross-site POSTs (CSRF).
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

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
ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


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


def _parse_amount(raw):
    """Return (Decimal, None) for a valid rupee amount, else (None, error)."""
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None, AMOUNT_FORMAT_ERROR
    if not amount.is_finite() or amount.as_tuple().exponent < -2:
        return None, AMOUNT_FORMAT_ERROR
    if amount <= 0 or amount > MAX_AMOUNT:
        return None, "Amount must be more than ₹0 and at most ₹1,00,00,000."
    return amount, None


def _validate_expense(form):
    """Validate an expense form (used by add now, edit in Step 8).

    Returns (values, clean, error). `values` always holds the stripped strings
    the user typed, so the form can echo them back. When error is None, `clean`
    holds the typed values ready to store ("amount" as a float); otherwise it
    is None.
    """
    values = {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }

    amount, error = _parse_amount(values["amount"])
    if error:
        return values, None, error

    if values["category"] not in CATEGORIES:
        return values, None, "Please choose a category."

    try:
        expense_date = _parse_date(values["date"])
    except ValueError:
        expense_date = None
    if not expense_date:
        return values, None, "Enter a valid date."
    # Both are zero-padded ISO strings, so comparing them as text is safe.
    if expense_date > date.today().isoformat():
        return values, None, "The date can't be in the future."

    if len(values["description"]) > MAX_DESCRIPTION:
        return values, None, f"Description must be {MAX_DESCRIPTION} characters or fewer."

    clean = {**values, "amount": float(round(amount, 2))}
    return values, clean, None


def _render_expense_form(values, error=None):
    """Render the expense form (shared by add now, edit in Step 8)."""
    return render_template(
        "add_expense.html",
        categories=CATEGORIES,
        today=date.today().isoformat(),
        max_amount=MAX_AMOUNT,
        max_description=MAX_DESCRIPTION,
        values=values,
        error=error,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if request.method == "GET":
        return _render_expense_form(
            {"amount": "", "category": "", "date": date.today().isoformat(),
             "description": ""}
        )

    values, clean, error = _validate_expense(request.form)
    if error:
        return _render_expense_form(values, error)

    try:
        create_expense(
            user_id,
            clean["amount"],
            clean["category"],
            clean["date"],
            clean["description"],
        )
    except sqlite3.IntegrityError:
        # The session points at a user that no longer exists (foreign key).
        session.clear()
        return redirect(url_for("login"))
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5001)
