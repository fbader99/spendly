"""Tests for Step 06: date filter on /profile.

Written from .claude/specs/06-date-filter-profile-page.md.
Page-level tests that need rows outside a range use empty_client plus rows
inserted here, keeping the visible range at 10 rows or fewer (the transaction
table keeps its limit of 10).
"""
import html as html_lib
import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from database.db import get_db
from database.queries import (
    get_category_breakdown,
    get_recent_transactions,
    get_summary_stats,
)

SEED_TOTAL = 6098.0  # 8 seeded demo expenses
SEED_COUNT = 8
SEED_TOTAL_TEXT = "₹6,098.00"
FLASH_TEXT = "Start date must be before end date."
PRESET_LABELS = ["This Month", "Last 3 Months", "Last 6 Months", "All Time"]


# --- helpers ---

def insert_expense(user_id, amount, category, on_date, description):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, on_date, description),
        )
        conn.commit()
    finally:
        conn.close()


def preset_tag(html, label):
    """Return the attribute string of the <a> whose text is `label`."""
    m = re.search(r"<a\b([^>]*)>\s*" + re.escape(label) + r"\s*</a>", html, re.S)
    assert m, f"preset link '{label}' not found in page"
    return m.group(1)


def preset_href(html, label):
    m = re.search(r'href="([^"]*)"', preset_tag(html, label))
    assert m, f"preset '{label}' has no href"
    return html_lib.unescape(m.group(1))


def tag_without_href(html, label):
    return re.sub(r'href="[^"]*"', "", preset_tag(html, label)).strip()


def shown_count(html):
    m = re.search(r"Transactions\s*</[^>]+>\s*<[^>]+>\s*(\d+)", html)
    assert m, "transaction count stat not found"
    return int(m.group(1))


def get_page(client, **params):
    return client.get("/profile", query_string=params)


@pytest.fixture
def range_rows(empty_user_id):
    """Rows for empty_user_id on explicit dates in 2020 (5 rows)."""
    rows = [
        ("2019-12-31", 10.0, "Food", "before-range"),
        ("2020-01-01", 100.0, "Food", "range-start"),
        ("2020-01-15", 200.0, "Bills", "range-middle"),
        ("2020-01-31", 300.0, "Food", "range-end"),
        ("2020-02-01", 1000.0, "Other", "after-range"),
    ]
    for d, amt, cat, desc in rows:
        insert_expense(empty_user_id, amt, cat, d, desc)
    return empty_user_id


# --- query helpers: unfiltered ---

class TestHelpersUnfiltered:
    def test_summary_stats_no_dates_returns_all_expenses(self, demo_user_id):
        stats = get_summary_stats(demo_user_id)
        assert stats["total_spent"] == pytest.approx(SEED_TOTAL)
        assert stats["transaction_count"] == SEED_COUNT

    def test_recent_transactions_no_dates_returns_all(self, demo_user_id):
        assert len(get_recent_transactions(demo_user_id)) == SEED_COUNT

    def test_category_breakdown_no_dates_returns_all(self, demo_user_id):
        cats = get_category_breakdown(demo_user_id)
        assert sum(c["amount"] for c in cats) == pytest.approx(SEED_TOTAL)

    def test_helpers_only_date_from_is_unfiltered(self, range_rows):
        # Filter applies only when both bounds are provided.
        assert get_summary_stats(range_rows, date_from="2020-01-15")["transaction_count"] == 5
        assert len(get_recent_transactions(range_rows, date_from="2020-01-15")) == 5

    def test_helpers_only_date_to_is_unfiltered(self, range_rows):
        assert get_summary_stats(range_rows, date_to="2020-01-15")["transaction_count"] == 5
        assert len(get_recent_transactions(range_rows, date_to="2020-01-15")) == 5
        cats = get_category_breakdown(range_rows, date_to="2020-01-15")
        assert sum(c["amount"] for c in cats) == pytest.approx(1610.0)


# --- query helpers: filtered ---

class TestHelpersFiltered:
    def test_summary_stats_range_is_inclusive_on_both_ends(self, range_rows):
        stats = get_summary_stats(range_rows, "2020-01-01", "2020-01-31")
        assert stats["transaction_count"] == 3, "start and end dates must be included"
        assert stats["total_spent"] == pytest.approx(600.0)

    def test_summary_stats_top_category_respects_range(self, range_rows):
        # Overall Other (1000) wins; within January Food (400) beats Bills (200).
        stats = get_summary_stats(range_rows, "2020-01-01", "2020-01-31")
        assert stats["top_category"] == "Food"

    def test_recent_transactions_range_excludes_outside_rows(self, range_rows):
        descs = [t["description"] for t in
                 get_recent_transactions(range_rows, date_from="2020-01-01", date_to="2020-01-31")]
        assert descs == ["range-end", "range-middle", "range-start"], (
            "expected in-range rows only, newest first"
        )

    def test_recent_transactions_limit_still_applies_with_range(self, range_rows):
        rows = get_recent_transactions(
            range_rows, limit=2, date_from="2020-01-01", date_to="2020-01-31"
        )
        assert [r["description"] for r in rows] == ["range-end", "range-middle"]

    def test_category_breakdown_respects_range(self, range_rows):
        cats = get_category_breakdown(range_rows, "2020-01-01", "2020-01-31")
        by_name = {c["name"]: c["amount"] for c in cats}
        assert by_name == {"Food": pytest.approx(400.0), "Bills": pytest.approx(200.0)}

    def test_single_day_range_returns_only_that_day(self, range_rows):
        stats = get_summary_stats(range_rows, "2020-01-15", "2020-01-15")
        assert stats["transaction_count"] == 1
        assert stats["total_spent"] == pytest.approx(200.0)

    def test_empty_range_returns_zero_values(self, demo_user_id):
        stats = get_summary_stats(demo_user_id, "2000-01-01", "2000-01-31")
        assert stats["total_spent"] == 0
        assert stats["transaction_count"] == 0
        assert get_recent_transactions(demo_user_id, date_from="2000-01-01", date_to="2000-01-31") == []
        assert get_category_breakdown(demo_user_id, "2000-01-01", "2000-01-31") == []

    def test_filter_does_not_leak_other_users_rows(self, range_rows, demo_user_id):
        stats = get_summary_stats(range_rows, "2020-01-01", "2020-01-31")
        assert stats["transaction_count"] == 3, "demo user's rows leaked into the range"
        demo_stats = get_summary_stats(demo_user_id, "2020-01-01", "2020-01-31")
        assert demo_stats["transaction_count"] == 0, "other user's rows leaked into demo's range"

    def test_category_pct_sums_to_100_under_filter(self, empty_user_id):
        for i, cat in enumerate(["Food", "Bills", "Health"]):
            insert_expense(empty_user_id, 100.0, cat, f"2020-03-0{i + 1}", f"third-{cat}")
        cats = get_category_breakdown(empty_user_id, "2020-03-01", "2020-03-31")
        assert len(cats) == 3
        assert sum(c["pct"] for c in cats) == 100, "pct must total 100 under a filter"

    def test_sql_injection_dates_are_treated_as_plain_text(self, demo_user_id):
        evil = "2020-01-01' OR '1'='1"
        get_summary_stats(demo_user_id, evil, "2099-12-31")  # must not raise
        # The expenses table must still exist and be intact.
        assert get_summary_stats(demo_user_id)["transaction_count"] == SEED_COUNT


# --- /profile: access ---

class TestAuth:
    @pytest.mark.parametrize("params", [
        {},
        {"date_from": "2020-01-01", "date_to": "2020-01-31"},
        {"date_from": "not-a-date"},
    ])
    def test_profile_signed_out_redirects_to_login(self, client, params):
        resp = client.get("/profile", query_string=params)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# --- /profile: no params ---

class TestNoParams:
    def test_profile_no_params_shows_all_expenses(self, logged_in_client):
        resp = get_page(logged_in_client)
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert SEED_TOTAL_TEXT in html, "total spent missing"
        assert shown_count(html) == SEED_COUNT

    def test_profile_no_params_shows_filter_bar(self, logged_in_client):
        html = get_page(logged_in_client).get_data(as_text=True)
        for label in PRESET_LABELS:
            assert label in html, f"preset '{label}' missing"
        assert 'type="date"' in html
        assert "Apply" in html


# --- presets ---

class TestPresets:
    def test_preset_links_exist_for_all_four_labels(self, logged_in_client):
        html = get_page(logged_in_client).get_data(as_text=True)
        for label in PRESET_LABELS:
            assert preset_href(html, label).startswith("/profile")

    def test_all_time_link_is_clean_profile_url(self, logged_in_client):
        html = get_page(logged_in_client).get_data(as_text=True)
        href = urlparse(preset_href(html, "All Time"))
        assert href.path == "/profile"
        assert href.query == "", "All Time must pass no query params"

    def test_this_month_link_params(self, logged_in_client):
        html = get_page(logged_in_client).get_data(as_text=True)
        q = parse_qs(urlparse(preset_href(html, "This Month")).query)
        today = date.today()
        assert q["date_from"] == [today.replace(day=1).isoformat()]
        assert q["date_to"] == [today.isoformat()]

    @pytest.mark.parametrize("label,min_days,max_days", [
        ("Last 3 Months", 88, 93),
        ("Last 6 Months", 180, 185),
    ])
    def test_multi_month_preset_link_params(self, logged_in_client, label, min_days, max_days):
        html = get_page(logged_in_client).get_data(as_text=True)
        q = parse_qs(urlparse(preset_href(html, label)).query)
        today = date.today()
        assert q["date_to"] == [today.isoformat()], "window must end today"
        start = date.fromisoformat(q["date_from"][0])
        assert min_days <= (today - start).days <= max_days, (
            f"{label} start {start} is not about that many months before today"
        )

    @pytest.mark.parametrize("label,in_offset,out_offset", [
        ("Last 3 Months", 30, 120),
        ("Last 6 Months", 150, 200),
    ])
    def test_following_multi_month_preset_filters_page(
        self, empty_client, empty_user_id, label, in_offset, out_offset
    ):
        today = date.today()
        insert_expense(empty_user_id, 111.0, "Food", today.isoformat(), "row-today")
        insert_expense(empty_user_id, 222.0, "Bills",
                       (today - timedelta(days=in_offset)).isoformat(), "row-inside")
        insert_expense(empty_user_id, 4000.0, "Other",
                       (today - timedelta(days=out_offset)).isoformat(), "row-outside")
        html = get_page(empty_client).get_data(as_text=True)
        resp = empty_client.get(preset_href(html, label))
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "row-today" in body and "row-inside" in body
        assert "row-outside" not in body, "row outside window shown"
        assert "₹333.00" in body, "total must cover in-window rows only"
        assert shown_count(body) == 2

    def test_following_this_month_preset_filters_all_sections(self, empty_client, empty_user_id):
        today = date.today()
        last_month_end = today.replace(day=1) - timedelta(days=1)
        insert_expense(empty_user_id, 500.0, "Food", today.isoformat(), "row-this-month")
        insert_expense(empty_user_id, 9000.0, "Other", last_month_end.isoformat(), "row-last-month")
        html = get_page(empty_client).get_data(as_text=True)
        body = empty_client.get(preset_href(html, "This Month")).get_data(as_text=True)
        assert "row-this-month" in body
        assert "row-last-month" not in body
        assert "₹500.00" in body
        assert "₹9,000.00" not in body, "out-of-range amount leaked into totals/breakdown"
        assert shown_count(body) == 1

    def test_following_all_time_preset_shows_everything(self, empty_client, empty_user_id):
        today = date.today()
        insert_expense(empty_user_id, 50.0, "Food", today.isoformat(), "row-new")
        insert_expense(empty_user_id, 70.0, "Food", (today - timedelta(days=400)).isoformat(), "row-old")
        # Start from a filtered view, then click All Time.
        filtered = get_page(empty_client, date_from=today.isoformat(), date_to=today.isoformat())
        href = preset_href(filtered.get_data(as_text=True), "All Time")
        body = empty_client.get(href).get_data(as_text=True)
        assert "row-new" in body and "row-old" in body
        assert "₹120.00" in body
        assert shown_count(body) == 2


# --- active state (loose: spec names no class) ---

class TestActiveState:
    # The spec only says the active preset is "visually highlighted". We assert
    # loosely that the active preset's markup (ignoring href) differs from the
    # inactive presets, without naming any CSS class.

    def test_all_time_highlighted_when_unfiltered(self, logged_in_client):
        html = get_page(logged_in_client).get_data(as_text=True)
        active = tag_without_href(html, "All Time")
        others = [tag_without_href(html, l) for l in PRESET_LABELS if l != "All Time"]
        assert all(active != o for o in others), "All Time not distinguished when unfiltered"

    @pytest.mark.parametrize("label", ["This Month", "Last 3 Months", "Last 6 Months"])
    def test_selected_preset_highlighted(self, logged_in_client, label):
        html = get_page(logged_in_client).get_data(as_text=True)
        href = preset_href(html, label)
        body = logged_in_client.get(href).get_data(as_text=True)
        active = tag_without_href(body, label)
        others = [tag_without_href(body, l) for l in PRESET_LABELS if l != label]
        assert all(active != o for o in others), f"'{label}' not distinguished when active"

    def test_custom_range_highlights_no_preset(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        tags = {tag_without_href(body, l) for l in PRESET_LABELS}
        assert len(tags) == 1, "no preset should be highlighted for a custom range"


# --- custom range ---

class TestCustomRange:
    def test_custom_range_filters_all_three_sections(self, empty_client, range_rows):
        body = get_page(empty_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        for desc in ("range-start", "range-middle", "range-end"):
            assert desc in body, f"{desc} should be shown"
        for desc in ("before-range", "after-range"):
            assert desc not in body, f"{desc} should be hidden"
        assert "₹600.00" in body, "total spent should cover the range only"
        assert "₹1,000.00" not in body, "out-of-range category amount leaked"
        assert shown_count(body) == 3

    def test_custom_range_form_prefilled_with_active_dates(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        for name, value in (("date_from", "2020-01-01"), ("date_to", "2020-01-31")):
            m = re.search(r'<input\b[^>]*name="%s"[^>]*>' % name, body, re.S)
            assert m, f"input {name} missing"
            assert 'type="date"' in m.group(0)
            assert f'value="{value}"' in m.group(0), f"{name} not pre-filled"

    def test_same_day_range_is_valid_and_not_an_error(self, empty_client, range_rows):
        body = get_page(empty_client, date_from="2020-01-15", date_to="2020-01-15").get_data(as_text=True)
        assert FLASH_TEXT not in body
        assert "range-middle" in body
        assert shown_count(body) == 1

    def test_filtered_page_still_shows_rupee_symbol(self, empty_client, range_rows):
        body = get_page(empty_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        assert "₹" in body

    def test_filtered_page_only_shows_own_data(self, logged_in_client, range_rows):
        # range_rows belong to another user; demo must not see them.
        body = get_page(logged_in_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        assert "range-middle" not in body
        assert shown_count(body) == 0

    def test_category_pct_sums_to_100_on_filtered_page(self, empty_client, empty_user_id):
        for i, cat in enumerate(["Food", "Bills", "Health"]):
            insert_expense(empty_user_id, 100.0, cat, f"2020-03-0{i + 1}", f"third-{cat}")
        assert get_page(empty_client, date_from="2020-03-01", date_to="2020-03-31").status_code == 200
        cats = get_category_breakdown(empty_user_id, "2020-03-01", "2020-03-31")
        assert sum(c["pct"] for c in cats) == 100


# --- invalid ranges and malformed input ---

class TestFallbacks:
    def test_start_after_end_flashes_error(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2020-02-01", date_to="2020-01-01").get_data(as_text=True)
        assert FLASH_TEXT in body, "flash error missing"

    def test_start_after_end_falls_back_to_unfiltered(self, logged_in_client):
        resp = get_page(logged_in_client, date_from="2099-02-01", date_to="2099-01-01")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert SEED_TOTAL_TEXT in body
        assert shown_count(body) == SEED_COUNT

    def test_start_after_end_does_not_prefill_form_with_rejected_dates(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2099-02-01", date_to="2099-01-01").get_data(as_text=True)
        assert "2099-02-01" not in body, "rejected dates must be treated as absent"

    def test_valid_range_shows_no_flash_error(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2020-01-01", date_to="2020-01-31").get_data(as_text=True)
        assert FLASH_TEXT not in body

    @pytest.mark.parametrize("bad", [
        "not-a-date",
        "2024-13-45",
        "2024-02-30",
        "2024/01/01",
        "01-01-2024",
        "' OR 1=1 --",
        "<script>x</script>",
        "x" * 500,
    ])
    def test_malformed_date_falls_back_silently(self, logged_in_client, bad):
        resp = get_page(logged_in_client, date_from=bad, date_to="2020-01-31")
        assert resp.status_code == 200, "malformed date must not crash"
        body = resp.get_data(as_text=True)
        assert SEED_TOTAL_TEXT in body, "should fall back to unfiltered view"
        assert shown_count(body) == SEED_COUNT
        assert FLASH_TEXT not in body, "malformed dates fall back silently"

    def test_both_dates_malformed_falls_back(self, logged_in_client):
        resp = get_page(logged_in_client, date_from="not-a-date", date_to="also-bad")
        assert resp.status_code == 200
        assert shown_count(resp.get_data(as_text=True)) == SEED_COUNT

    @pytest.mark.parametrize("params", [
        {"date_from": "2000-01-01"},
        {"date_to": "2000-01-31"},
        {"date_from": "", "date_to": ""},
    ])
    def test_missing_or_partial_params_fall_back_to_unfiltered(self, logged_in_client, params):
        resp = get_page(logged_in_client, **params)
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert SEED_TOTAL_TEXT in body
        assert shown_count(body) == SEED_COUNT


# --- empty range ---

class TestEmptyRange:
    def test_empty_range_shows_zero_total_and_count(self, logged_in_client):
        resp = get_page(logged_in_client, date_from="2000-01-01", date_to="2000-01-31")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "₹0.00" in body, "zero total missing"
        assert shown_count(body) == 0
        assert SEED_TOTAL_TEXT not in body

    def test_empty_range_hides_transactions_and_breakdown(self, logged_in_client):
        body = get_page(logged_in_client, date_from="2000-01-01", date_to="2000-01-31").get_data(as_text=True)
        for desc in ("Electricity bill", "Groceries for the week", "New running shoes"):
            assert desc not in body, f"'{desc}' should not appear in an empty range"
        assert "₹2,200.00" not in body, "category amount shown for empty range"

    def test_empty_user_unfiltered_and_filtered_do_not_error(self, empty_client):
        assert get_page(empty_client).status_code == 200
        resp = get_page(empty_client, date_from="2020-01-01", date_to="2020-12-31")
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert "₹0.00" in body
        assert shown_count(body) == 0
