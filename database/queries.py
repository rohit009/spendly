"""Read-only query helpers for the profile page (no Flask imports).

Every helper opens its own connection with get_db() and closes it before
returning. All SQL is parameterised and scoped to a single user_id.

The file is split into marked sections so that several people can fill in
different functions at the same time. Only edit inside your own section.
"""
from datetime import datetime

from database.db import get_db


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
def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in rows
    ]
# === END SECTION 1 =========================================================


# === SECTION 2: SUMMARY STATS (SubAgent-2) =================================
def get_summary_stats(user_id):
    """Return {total_spent, transaction_count, top_category} for the user."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC, category ASC LIMIT 1",
            (user_id,),
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
def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id,),
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
