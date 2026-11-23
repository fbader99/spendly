"""Tests for Step 8: Edit Expense (spec: .claude/specs/08-edit-expense.md)."""
import pytest

from database.db import get_db
from database.queries import get_expense_by_id, insert_expense, update_expense

VALID_FORM = {
    "amount": "99.50",
    "category": "Transport",
    "date": "2026-04-15",
    "description": "Taxi home",
}


# --- helpers ---------------------------------------------------------------

def _get_row(expense_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _snapshot(expense_id):
    row = _get_row(expense_id)
    return (row["amount"], row["category"], row["date"], row["description"])


def _form(**overrides):
    data = dict(VALID_FORM)
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


@pytest.fixture
def own_expense_id(demo_user_id):
    return insert_expense(demo_user_id, 450.0, "Food", "2026-03-01", "Groceries")


@pytest.fixture
def other_expense_id(empty_user_id):
    return insert_expense(empty_user_id, 75.0, "Bills", "2026-03-02", "Not yours")


def _url(expense_id):
    return f"/expenses/{expense_id}/edit"


# --- unit: get_expense_by_id -------------------------------------------------

def test_get_expense_by_id_own(own_expense_id, demo_user_id):
    expense = get_expense_by_id(own_expense_id, demo_user_id)
    assert expense == {
        "id": own_expense_id,
        "amount": 450.0,
        "category": "Food",
        "date": "2026-03-01",
        "description": "Groceries",
    }


def test_get_expense_by_id_wrong_user(other_expense_id, demo_user_id):
    assert get_expense_by_id(other_expense_id, demo_user_id) is None


def test_get_expense_by_id_missing(demo_user_id):
    assert get_expense_by_id(999999, demo_user_id) is None


# --- unit: update_expense ----------------------------------------------------

def test_update_expense_own(own_expense_id, demo_user_id):
    assert update_expense(own_expense_id, demo_user_id, 99.0, "Health",
                          "2026-03-05", "Doctor") is True
    assert _snapshot(own_expense_id) == (99.0, "Health", "2026-03-05", "Doctor")


def test_update_expense_wrong_user(other_expense_id, demo_user_id):
    before = _snapshot(other_expense_id)
    assert update_expense(other_expense_id, demo_user_id, 1.0, "Food",
                          "2026-01-01", "hijack") is False
    assert _snapshot(other_expense_id) == before


def test_update_expense_null_description(own_expense_id, demo_user_id):
    update_expense(own_expense_id, demo_user_id, 10.0, "Food", "2026-03-01", None)
    assert _get_row(own_expense_id)["description"] is None


# --- routes: auth ------------------------------------------------------------

def test_get_logged_out_redirects(client, own_expense_id):
    resp = client.get(_url(own_expense_id))
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_logged_out_redirects(client, own_expense_id):
    before = _snapshot(own_expense_id)
    resp = client.post(_url(own_expense_id), data=_form())
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _snapshot(own_expense_id) == before


# --- routes: GET -------------------------------------------------------------

def test_get_own_prefilled(logged_in_client, own_expense_id):
    resp = logged_in_client.get(_url(own_expense_id))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'value="450.00"' in html
    assert 'value="2026-03-01"' in html
    assert 'value="Groceries"' in html
    assert '<option value="Food" selected>' in html
    assert f'action="{_url(own_expense_id)}"' in html
    assert "Save Changes" in html


def test_get_other_users_expense_404(logged_in_client, other_expense_id):
    assert logged_in_client.get(_url(other_expense_id)).status_code == 404


def test_get_missing_expense_404(logged_in_client):
    assert logged_in_client.get(_url(999999)).status_code == 404


# --- routes: POST ------------------------------------------------------------

def test_post_valid_updates(logged_in_client, own_expense_id):
    resp = logged_in_client.post(_url(own_expense_id), data=_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    assert _snapshot(own_expense_id) == (99.5, "Transport", "2026-04-15", "Taxi home")


def test_post_valid_flashes_success(logged_in_client, own_expense_id):
    resp = logged_in_client.post(_url(own_expense_id), data=_form(),
                                 follow_redirects=True)
    assert "Expense updated." in resp.get_data(as_text=True)


def test_post_other_users_expense_404(logged_in_client, other_expense_id):
    before = _snapshot(other_expense_id)
    resp = logged_in_client.post(_url(other_expense_id), data=_form())
    assert resp.status_code == 404
    assert _snapshot(other_expense_id) == before


@pytest.mark.parametrize("overrides", [
    {"amount": None},
    {"amount": "0"},
    {"amount": "abc"},
    {"category": "Rent"},
    {"date": "not-a-date"},
])
def test_post_invalid_rerenders(logged_in_client, own_expense_id, overrides):
    before = _snapshot(own_expense_id)
    resp = logged_in_client.post(_url(own_expense_id), data=_form(**overrides))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'class="auth-error"' in html
    assert _snapshot(own_expense_id) == before


def test_post_invalid_keeps_submitted_values(logged_in_client, own_expense_id):
    resp = logged_in_client.post(_url(own_expense_id), data=_form(amount="0"))
    html = resp.get_data(as_text=True)
    assert 'value="Taxi home"' in html
    assert 'value="2026-04-15"' in html
    assert '<option value="Transport" selected>' in html


def test_post_blank_description_stores_null(logged_in_client, own_expense_id):
    resp = logged_in_client.post(_url(own_expense_id), data=_form(description="   "))
    assert resp.status_code == 302
    assert _get_row(own_expense_id)["description"] is None


# --- profile edit links ------------------------------------------------------

def test_profile_has_edit_link_per_row(logged_in_client, demo_user_id):
    conn = get_db()
    try:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM expenses WHERE user_id = ?", (demo_user_id,))]
    finally:
        conn.close()

    html = logged_in_client.get("/profile").get_data(as_text=True)
    for expense_id in ids:
        assert f'href="{_url(expense_id)}"' in html
