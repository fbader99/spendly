from datetime import datetime

import pytest

from database.db import CATEGORIES
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
)

SEED_TOTAL = 6098.0  # sum of the 8 amounts inserted by seed_db()


# --- get_user_by_id ---

def test_get_user_by_id_valid(demo_user_id):
    user = get_user_by_id(demo_user_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    # created_at defaults to datetime('now') (UTC), so compare month names loosely.
    datetime.strptime(user["member_since"], "%B %Y")


def test_get_user_by_id_missing():
    assert get_user_by_id(99999) is None


def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_shows_real_user(logged_in_client):
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Demo User" in html
    assert "demo@spendly.com" in html
    assert "₹" in html


def test_profile_stale_session_redirects(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
        sess["user_name"] = "Ghost"
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# --- transaction history ---

def test_get_recent_transactions_demo_user(demo_user_id):
    txns = get_recent_transactions(demo_user_id)
    assert len(txns) == 8
    for t in txns:
        assert isinstance(t, dict)
        assert set(t) == {"date", "description", "category", "amount"}
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert sum(t["amount"] for t in txns) == SEED_TOTAL


def test_get_recent_transactions_respects_limit(demo_user_id):
    assert len(get_recent_transactions(demo_user_id, limit=3)) == 3


def test_get_recent_transactions_empty_user(empty_user_id):
    assert get_recent_transactions(empty_user_id) == []


def test_profile_shows_recent_transactions_newest_first(logged_in_client, demo_user_id):
    resp = logged_in_client.get("/profile")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    txns = get_recent_transactions(demo_user_id)
    for t in txns:
        assert t["description"] in html
    # Walk the HTML forward: each row's date must appear after the previous
    # row's position (handles several expenses sharing a date).
    pos = 0
    for t in txns:
        pos = html.index(t["date"], pos)
        pos = html.index(t["description"], pos)



# --- summary stats ---



def test_summary_stats_demo_user(demo_user_id):
    stats = get_summary_stats(demo_user_id)
    assert stats["total_spent"] == pytest.approx(SEED_TOTAL)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_summary_stats_empty_user(empty_user_id):
    assert get_summary_stats(empty_user_id) == {
        "total_spent": 0,
        "transaction_count": 0,
        "top_category": "—",
    }


def test_profile_summary_stats_demo(logged_in_client):
    resp = logged_in_client.get("/profile")
    assert "₹6,098.00" in resp.get_data(as_text=True)


def test_profile_summary_stats_empty(empty_client):
    resp = empty_client.get("/profile")
    assert resp.status_code == 200
    assert "₹0.00" in resp.get_data(as_text=True)



# --- category breakdown ---

def test_category_breakdown_demo_user(demo_user_id):
    cats = get_category_breakdown(demo_user_id)
    assert len(cats) == 7
    amounts = [c["amount"] for c in cats]
    assert amounts == sorted(amounts, reverse=True)
    assert cats[0]["name"] == "Bills"
    assert cats[0]["amount"] == 2200.0
    by_name = {c["name"]: c["amount"] for c in cats}
    assert by_name["Food"] == 730.0
    assert all(isinstance(c["pct"], int) for c in cats)
    assert sum(c["pct"] for c in cats) == 100


def test_category_breakdown_empty_user(empty_user_id):
    assert get_category_breakdown(empty_user_id) == []


def test_profile_shows_category_breakdown(logged_in_client):

    assert len(CATEGORIES) == 7
    html = logged_in_client.get("/profile").get_data(as_text=True)
    for name in CATEGORIES:
        assert name in html
    assert "₹730.00" in html

