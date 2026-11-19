"""Query helpers for the profile and expense pages (no Flask imports).

All helpers are read-only except create_expense (Step 7). Every helper
opens its own connection with get_db() and closes it before returning.
All SQL is parameterised and scoped to a single user_id.

The file is split into marked sections so that several people can fill in
different functions at the same time. Only edit inside your own section.
"""
from datetime import datetime

from database.db import get_db


def _date_clause(date_from, date_to):
    """Return (sql, params) for an optional inclusive date range.

    The SQL is built only from fixed strings; the dates travel as parameters.
    Dates are ISO YYYY-MM-DD text, so string comparison orders them correctly.
    """
    sql, params = "", []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    return sql, params


def get_user_by_id(user_id):
    """Return {name, email, initials, member_since} or None if no such user."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    initials = "".join(word[0] for word in row["name"].split()[:2]).upper()
    created = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    return {
        "name": row["name"],
        "email": row["email"],
        "initials": initials,
        "member_since": created.strftime("%B %Y"),
    }


# === SECTION 1: TRANSACTION HISTORY (SubAgent-1) ===========================
def get_recent_transactions(user_id, limit=10, date_from=None, date_to=None):
    """Return up to `limit` newest expenses, optionally within an inclusive date range."""
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ?"
            + clause
            + " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row["id"],
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]
# === END SECTION 1 =========================================================


# === SECTION 2: SUMMARY STATS (SubAgent-2) =================================
def get_summary_stats(user_id, date_from=None, date_to=None):
    """Return {total_spent, transaction_count, top_category} for the user."""
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?" + clause,
            (user_id, *params),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ?"
            + clause
            + " GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id, *params),
        ).fetchone()
    finally:
        conn.close()

    if totals["cnt"] == 0 or top is None:
        return {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
    return {
        "total_spent": round(float(totals["total"]), 2),
        "transaction_count": int(totals["cnt"]),
        "top_category": top["category"],
    }
# === END SECTION 2 =========================================================


# === SECTION 3: CATEGORY BREAKDOWN (SubAgent-3) ============================
def get_category_breakdown(user_id, date_from=None, date_to=None):
    """Return [{name, amount, pct}] by amount, optionally within an inclusive date range."""
    clause, params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ?"
            + clause
            + " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id, *params),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(r["total"] for r in rows)
    if not rows or not grand_total:
        return []

    result = [
        {
            "name": r["category"],
            "amount": round(r["total"], 2),
            "pct": int(round(r["total"] * 100 / grand_total)),
        }
        for r in rows
    ]
    result[0]["pct"] += 100 - sum(item["pct"] for item in result)
    return result
# === END SECTION 3 =========================================================


# === SECTION 4: ADD EXPENSE (Step 7) =======================================
def create_expense(user_id, amount, category, date, description=None):
    """Insert one expense for user_id and return its new id.

    The caller must validate the values first; this only writes them.
    A blank description is stored as NULL.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description or None),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
# === END SECTION 4 =========================================================


# === SECTION 5: EDIT EXPENSE (Step 8) ======================================
def get_expense(user_id, expense_id):
    """Return one expense as a dict, or None if it is missing or not user_id's."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row else None


def update_expense(user_id, expense_id, amount, category, date, description=None):
    """Update one expense owned by user_id. Return True if a row was changed.

    The caller must validate the values first. user_id and created_at are
    never modified; a blank description is stored as NULL.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, "
            "description = ? WHERE id = ? AND user_id = ?",
            (amount, category, date, description or None, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()
# === END SECTION 5 =========================================================


# === SECTION 6: DELETE EXPENSE (Step 9) ====================================
def delete_expense_row(user_id, expense_id):
    """Delete one expense owned by user_id. Return True if a row was deleted."""
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()
# === END SECTION 6 =========================================================
