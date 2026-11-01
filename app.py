import os
import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

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


# Hardcoded demo data for the profile page UI (Step 4). Step 5 replaces this
# with real queries against the logged-in user's rows.
PROFILE_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "initials": "DU",
    "member_since": "January 2026",
}

PROFILE_TRANSACTIONS = [
    {"date": "25 Oct 2026", "description": "Dinner out", "category": "Food", "amount": 780},
    {"date": "20 Oct 2026", "description": "Gift", "category": "Other", "amount": 300},
    {"date": "15 Oct 2026", "description": "Shoes", "category": "Shopping", "amount": 2299},
    {"date": "12 Oct 2026", "description": "Movie tickets", "category": "Entertainment", "amount": 499},
    {"date": "08 Oct 2026", "description": "Pharmacy", "category": "Health", "amount": 650},
    {"date": "05 Oct 2026", "description": "Electricity bill", "category": "Bills", "amount": 1850},
    {"date": "03 Oct 2026", "description": "Auto rickshaw", "category": "Transport", "amount": 120},
    {"date": "01 Oct 2026", "description": "Groceries", "category": "Food", "amount": 450},
]


def _profile_summary(transactions):
    totals = {}
    for t in transactions:
        totals[t["category"]] = totals.get(t["category"], 0) + t["amount"]
    grand_total = sum(totals.values())
    categories = [
        {"name": name, "total": total, "percent": round(total * 100 / grand_total)}
        for name, total in sorted(totals.items(), key=lambda item: -item[1])
    ]
    stats = {
        "total_spent": grand_total,
        "count": len(transactions),
        "top_category": categories[0]["name"] if categories else None,
    }
    return stats, categories


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    stats, categories = _profile_summary(PROFILE_TRANSACTIONS)
    return render_template(
        "profile.html",
        user=PROFILE_USER,
        stats=stats,
        transactions=PROFILE_TRANSACTIONS,
        categories=categories,
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
