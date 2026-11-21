"""Tests for Step 7: Add Expense (spec: .claude/specs/07-add-expense.md)."""
import re

import pytest

from database.db import CATEGORIES, create_user, get_db
from database.queries import insert_expense

EXPECTED_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]

VALID_FORM = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


# --- helpers ---------------------------------------------------------------

def _count_expenses(user_id=None):
    conn = get_db()
    try:
        if user_id is None:
            return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
    finally:
        conn.close()


def _rows_with_description(description):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE description = ?", (description,)
        ).fetchall()
    finally:
        conn.close()


def _latest_expense(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _form(**overrides):
    data = dict(VALID_FORM)
    data.update(overrides)
    # Drop keys explicitly set to None to simulate a missing field.
    return {k: v for k, v in data.items() if v is not None}


# --- insert_expense unit tests ---------------------------------------------

class TestInsertExpense:
    def test_insert_expense_valid_data_creates_row(self, demo_user_id):
        before = _count_expenses(demo_user_id)
        insert_expense(demo_user_id, 50.0, "Food", "2026-03-20", "Lunch")

        assert _count_expenses(demo_user_id) == before + 1, "row not inserted"
        row = _latest_expense(demo_user_id)
        assert row["user_id"] == demo_user_id
        assert row["amount"] == pytest.approx(50.0)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    def test_insert_expense_description_none_stores_null(self, demo_user_id):
        insert_expense(demo_user_id, 12.5, "Bills", "2026-03-21", None)

        row = _latest_expense(demo_user_id)
        assert row["description"] is None, "description should be stored as NULL"
        assert row["amount"] == pytest.approx(12.5)

    def test_insert_expense_sql_injection_description_stored_as_text(self, demo_user_id):
        payload = "x'); DROP TABLE expenses;--"
        insert_expense(demo_user_id, 5.0, "Other", "2026-03-22", payload)

        assert _latest_expense(demo_user_id)["description"] == payload
        assert _count_expenses() > 0, "expenses table was damaged"


# --- GET /expenses/add ------------------------------------------------------

class TestAddExpenseGet:
    def test_get_signed_out_redirects_to_login(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_get_signed_in_returns_200(self, logged_in_client):
        resp = logged_in_client.get("/expenses/add")
        assert resp.status_code == 200

    def test_get_signed_in_contains_post_form(self, logged_in_client):
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        form_tag = re.search(r"<form[^>]*>", html, re.IGNORECASE)
        assert form_tag, "no <form> element found"
        assert re.search(r'method="?post"?', form_tag.group(0), re.IGNORECASE), (
            "form method is not POST"
        )

    def test_get_signed_in_form_has_all_fields(self, logged_in_client):
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        for field in ("amount", "category", "date", "description"):
            assert f'name="{field}"' in html, f"field {field} missing from form"

    def test_get_signed_in_category_select_has_all_seven_options(self, logged_in_client):
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        select = re.search(
            r"<select[^>]*name=\"category\"[^>]*>(.*?)</select>", html,
            re.IGNORECASE | re.DOTALL,
        )
        assert select, "category <select> missing"
        values = re.findall(r'<option[^>]*value="([^"]*)"', select.group(1))
        values = [v for v in values if v]  # ignore the blank placeholder
        assert values == EXPECTED_CATEGORIES, f"unexpected categories: {values}"

    def test_categories_constant_matches_spec(self):
        assert list(CATEGORIES) == EXPECTED_CATEGORIES

    def test_get_signed_in_date_defaults_to_today(self, logged_in_client):
        from datetime import date

        # Read today on both sides of the request so a midnight rollover can't flake.
        before = date.today().isoformat()
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        after = date.today().isoformat()
        assert before in html or after in html, "date should default to today"

    def test_get_signed_in_has_cancel_link_to_profile(self, logged_in_client):
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        assert 'href="/profile"' in html, "cancel link to /profile missing"

    def test_get_signed_in_has_save_button(self, logged_in_client):
        html = logged_in_client.get("/expenses/add").get_data(as_text=True)
        assert "Save Expense" in html


# --- POST auth guard --------------------------------------------------------

class TestAddExpensePostAuth:
    def test_post_signed_out_redirects_to_login_and_inserts_nothing(self, client):
        before = _count_expenses()
        resp = client.post("/expenses/add", data=_form())
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")
        assert _count_expenses() == before, "row inserted for signed-out user"
        assert _rows_with_description("Lunch") == []


# --- POST happy path --------------------------------------------------------

class TestAddExpensePostValid:
    def test_post_valid_redirects_and_inserts_row(self, logged_in_client, demo_user_id):
        before = _count_expenses(demo_user_id)
        resp = logged_in_client.post("/expenses/add", data=_form())

        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert _count_expenses(demo_user_id) == before + 1
        row = _latest_expense(demo_user_id)
        assert row["amount"] == pytest.approx(50.0)
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"

    @pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
    def test_post_valid_every_category_accepted(self, logged_in_client, demo_user_id, category):
        resp = logged_in_client.post("/expenses/add", data=_form(category=category))
        assert resp.status_code == 302, f"{category} rejected"
        assert _latest_expense(demo_user_id)["category"] == category

    def test_post_no_description_stores_null(self, logged_in_client, demo_user_id):
        resp = logged_in_client.post("/expenses/add", data=_form(description=None))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")
        assert _latest_expense(demo_user_id)["description"] is None

    @pytest.mark.parametrize("blank", ["", "   "])
    def test_post_blank_description_stores_null(self, logged_in_client, demo_user_id, blank):
        resp = logged_in_client.post("/expenses/add", data=_form(description=blank))
        assert resp.status_code == 302
        assert _latest_expense(demo_user_id)["description"] is None, (
            "blank description should be stored as NULL"
        )

    def test_post_description_is_stripped(self, logged_in_client, demo_user_id):
        logged_in_client.post("/expenses/add", data=_form(description="  Tea  "))
        assert _latest_expense(demo_user_id)["description"] == "Tea"

    def test_post_amount_rounded_to_two_places(self, logged_in_client, demo_user_id):
        logged_in_client.post("/expenses/add", data=_form(amount="250.456"))
        assert _latest_expense(demo_user_id)["amount"] == pytest.approx(250.46)

    def test_post_unpadded_date_is_stored_normalised(self, logged_in_client, demo_user_id):
        resp = logged_in_client.post("/expenses/add", data=_form(date="2026-3-5"))
        assert resp.status_code == 302
        assert _latest_expense(demo_user_id)["date"] == "2026-03-05"

    def test_post_new_expense_appears_on_profile(self, logged_in_client):
        logged_in_client.post(
            "/expenses/add",
            data=_form(amount="1234.56", description="Zebra-unique-note"),
        )
        html = logged_in_client.get("/profile").get_data(as_text=True)
        assert "Zebra-unique-note" in html, "new expense description not on profile"
        assert "₹1,234.56" in html, "new expense amount not on profile"

    def test_post_follow_redirect_lands_on_profile(self, logged_in_client):
        resp = logged_in_client.post("/expenses/add", data=_form(), follow_redirects=True)
        assert resp.status_code == 200
        assert "Lunch" in resp.get_data(as_text=True)


# --- POST validation errors -------------------------------------------------

INVALID_CASES = [
    pytest.param({"amount": None}, id="missing-amount"),
    pytest.param({"amount": ""}, id="empty-amount"),
    pytest.param({"amount": "0"}, id="zero-amount"),
    pytest.param({"amount": "-5"}, id="negative-amount"),
    pytest.param({"amount": "abc"}, id="non-numeric-amount"),
    pytest.param({"amount": "nan"}, id="nan-amount"),
    pytest.param({"amount": "inf"}, id="inf-amount"),
    pytest.param({"amount": "1e300"}, id="huge-amount"),
    pytest.param({"category": "Gambling"}, id="invalid-category"),
    pytest.param({"category": None}, id="missing-category"),
    pytest.param({"date": "not-a-date"}, id="invalid-date-string"),
    pytest.param({"date": "2026-13-45"}, id="impossible-date"),
    pytest.param({"date": None}, id="missing-date"),
]


class TestAddExpensePostInvalid:
    @pytest.mark.parametrize("overrides", INVALID_CASES)
    def test_post_invalid_rerenders_form_with_error_and_no_insert(
        self, logged_in_client, overrides
    ):
        before = _count_expenses()
        resp = logged_in_client.post(
            "/expenses/add", data=_form(description="Invalid-case-marker", **overrides)
        )
        html = resp.get_data(as_text=True)

        assert resp.status_code == 200, "invalid input should re-render the form"
        assert "<form" in html, "form not re-rendered"
        assert "auth-error" in html, "error message element missing"
        assert _count_expenses() == before, "row inserted despite invalid input"
        assert _rows_with_description("Invalid-case-marker") == []

    def test_post_description_over_200_chars_rejected(self, logged_in_client):
        before = _count_expenses()
        resp = logged_in_client.post("/expenses/add", data=_form(description="x" * 201))
        assert resp.status_code == 200
        assert "auth-error" in resp.get_data(as_text=True)
        assert _count_expenses() == before, "row inserted despite long description"

    def test_post_description_of_exactly_200_chars_accepted(self, logged_in_client, demo_user_id):
        resp = logged_in_client.post("/expenses/add", data=_form(description="y" * 200))
        assert resp.status_code == 302
        assert _latest_expense(demo_user_id)["description"] == "y" * 200

    def test_post_missing_amount_keeps_other_values(self, logged_in_client):
        resp = logged_in_client.post(
            "/expenses/add",
            data=_form(amount="", category="Health", date="2026-02-14",
                       description="Keep me"),
        )
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "Keep me" in html, "description not retained"
        assert "2026-02-14" in html, "date not retained"
        selected = re.search(
            r'<option[^>]*value="Health"[^>]*selected', html, re.IGNORECASE
        )
        assert selected, "category not retained"

    def test_post_zero_amount_keeps_entered_values(self, logged_in_client):
        resp = logged_in_client.post(
            "/expenses/add",
            data=_form(amount="0", category="Shopping", date="2026-01-05",
                       description="Zero retained"),
        )
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'value="0"' in html, "amount not retained"
        assert "Zero retained" in html
        assert "2026-01-05" in html
        assert re.search(r'<option[^>]*value="Shopping"[^>]*selected', html), (
            "category not retained"
        )

    def test_post_invalid_category_keeps_amount_and_description(self, logged_in_client):
        resp = logged_in_client.post(
            "/expenses/add",
            data=_form(amount="77.25", category="Bogus", description="Retain this"),
        )
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'value="77.25"' in html, "amount not retained"
        assert "Retain this" in html

    def test_post_invalid_date_keeps_amount_and_description(self, logged_in_client):
        resp = logged_in_client.post(
            "/expenses/add",
            data=_form(amount="19.99", date="31/12/2026", description="Date retained"),
        )
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'value="19.99"' in html, "amount not retained"
        assert "Date retained" in html

    def test_post_invalid_signed_out_still_redirects_to_login(self, client):
        resp = client.post("/expenses/add", data=_form(amount="0"))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")


# --- user isolation ---------------------------------------------------------

class TestAddExpenseIsolation:
    def test_expense_belongs_to_session_user_not_other_user(
        self, logged_in_client, demo_user_id, empty_user_id
    ):
        before_empty = _count_expenses(empty_user_id)
        logged_in_client.post("/expenses/add", data=_form(description="Demo-only-note"))

        assert _count_expenses(empty_user_id) == before_empty
        rows = _rows_with_description("Demo-only-note")
        assert len(rows) == 1
        assert rows[0]["user_id"] == demo_user_id

    def test_posted_user_id_field_is_ignored(
        self, logged_in_client, demo_user_id, empty_user_id
    ):
        logged_in_client.post(
            "/expenses/add",
            data=_form(description="Spoof-attempt", user_id=str(empty_user_id)),
        )
        rows = _rows_with_description("Spoof-attempt")
        assert len(rows) == 1
        assert rows[0]["user_id"] == demo_user_id, "user_id must come from session"

    def test_added_expense_not_visible_on_other_users_profile(
        self, client, demo_user_id, empty_user_id
    ):
        with client.session_transaction() as sess:
            sess["user_id"] = demo_user_id
            sess["user_name"] = "Demo User"
        client.post("/expenses/add", data=_form(description="Private-note-xyz"))

        with client.session_transaction() as sess:
            sess["user_id"] = empty_user_id
            sess["user_name"] = "Empty User"
        html = client.get("/profile").get_data(as_text=True)
        assert "Private-note-xyz" not in html, "expense leaked to another user"

    def test_empty_user_can_add_expense_and_see_it(self, empty_client, empty_user_id):
        resp = empty_client.post(
            "/expenses/add", data=_form(description="First-ever-expense")
        )
        assert resp.status_code == 302
        assert _count_expenses(empty_user_id) == 1
        html = empty_client.get("/profile").get_data(as_text=True)
        assert "First-ever-expense" in html

    def test_second_registered_user_expense_not_on_demo_profile(
        self, logged_in_client
    ):
        other_id = create_user("Other Person", "other@example.com", "password123")
        insert_expense(other_id, 99.0, "Other", "2026-03-01", "Other-user-note")
        html = logged_in_client.get("/profile").get_data(as_text=True)
        assert "Other-user-note" not in html


# --- navigation links -------------------------------------------------------

class TestAddExpenseLinks:
    def test_profile_has_add_expense_link(self, logged_in_client):
        html = logged_in_client.get("/profile").get_data(as_text=True)
        assert re.search(r'<a[^>]*href="/expenses/add"[^>]*>', html), (
            "link to /expenses/add missing on profile"
        )
        assert "Add Expense" in html

    def test_navbar_shows_add_expense_when_logged_in(self, logged_in_client):
        html = logged_in_client.get("/profile").get_data(as_text=True)
        nav = re.search(r"<nav.*?</nav>", html, re.IGNORECASE | re.DOTALL)
        assert nav, "no <nav> found"
        assert "Add Expense" in nav.group(0), "navbar link missing when logged in"
        assert "/expenses/add" in nav.group(0)

    @pytest.mark.parametrize("path", ["/", "/login", "/register"])
    def test_navbar_hides_add_expense_when_logged_out(self, client, path):
        html = client.get(path).get_data(as_text=True)
        assert "Add Expense" not in html, f"Add Expense shown when logged out on {path}"
        assert "/expenses/add" not in html

    def test_navbar_shows_add_expense_on_landing_when_logged_in(self, logged_in_client):
        html = logged_in_client.get("/").get_data(as_text=True)
        assert "Add Expense" in html


# --- HTTP semantics ---------------------------------------------------------

class TestAddExpenseHttp:
    @pytest.mark.parametrize("method", ["put", "delete", "patch"])
    def test_unsupported_methods_return_405(self, logged_in_client, method):
        resp = getattr(logged_in_client, method)("/expenses/add")
        assert resp.status_code == 405
