"""Read-only query helpers for the profile page.

Pure functions (no Flask imports). Each opens its own connection with
get_db() and closes it before returning.
"""
from datetime import datetime

from database.db import get_db


def get_user_by_id(user_id):
    """Return {"name", "email", "member_since"} for this user, or None."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    member_since = datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    return {"name": row["name"], "email": row["email"], "member_since": member_since}


# --- transaction history ---

def get_recent_transactions(user_id, limit=10):
    """Return up to `limit` of this user's expenses, newest first.

    Each item is {"date", "description", "category", "amount"}; [] if none.
    """
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
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"],
        }
        for row in rows
    ]


# --- summary stats ---

def get_summary_stats(user_id):
    """Return {"total_spent", "transaction_count", "top_category"} for this user.

    top_category is the category with the highest summed amount, or "—"
    when the user has no expenses.
    """
    conn = get_db()
    try:
        total, count = conn.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {
        "total_spent": total,
        "transaction_count": count,
        "top_category": top["category"] if top else "—",
    }


# --- category breakdown ---

def get_category_breakdown(user_id):
    """Return spending per category as [{"name", "amount", "pct"}], largest first.

    pct values are whole numbers that sum to exactly 100 (the rounding
    remainder goes to the largest category). Empty list if no expenses.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)
    if not rows or grand_total <= 0:
        return []

    categories = [
        {
            "name": row["category"],
            "amount": row["total"],
            "pct": int(round(row["total"] / grand_total * 100)),
        }
        for row in rows
    ]
    categories[0]["pct"] += 100 - sum(c["pct"] for c in categories)
    return categories
