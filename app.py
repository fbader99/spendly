import calendar
import math
import sqlite3
from datetime import date, datetime
from functools import wraps

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import CATEGORIES, create_user, get_user_by_email, init_db, seed_db
from database.queries import (
    delete_expense as delete_expense_row,
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
    update_expense,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # dev only; needed for flash()

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

def _parse_iso_date(value):
    """Return a date for a YYYY-MM-DD string, or None if missing or malformed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _months_ago(d, n):
    """Return the same day n months before d, clamped to that month's last day."""
    month_index = d.year * 12 + (d.month - 1) - n
    year, month = divmod(month_index, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _date_presets(today):
    """Return the quick-select filter presets as ISO-string date ranges."""
    def preset(key, label, start):
        return {
            "key": key,
            "label": label,
            "date_from": start.isoformat() if start else None,
            "date_to": today.isoformat() if start else None,
        }

    return [
        preset("this-month", "This Month", today.replace(day=1)),
        preset("last-3-months", "Last 3 Months", _months_ago(today, 3)),
        preset("last-6-months", "Last 6 Months", _months_ago(today, 6)),
        preset("all-time", "All Time", None),
    ]


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #

def login_required(view):
    """Redirect to the login page unless a user is signed in."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


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

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not name or not email or not password or not confirm_password:
            flash("All fields are required.", "error")
            return render_template("register.html", name=name, email=email)

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html", name=name, email=email)

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("Email already registered.", "error")
            return render_template("register.html", name=name, email=email)

        flash("Account created! Please sign in.", "success")
        return redirect(url_for("login"))

    abort(405)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html", email=email)

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("profile"))

    abort(405)


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


@app.route("/profile")
@login_required
def profile():
    user_id = session["user_id"]
    user = get_user_by_id(user_id)
    if user is None:
        # Stale session: the user no longer exists (e.g. the DB was reset).
        session.clear()
        return redirect(url_for("login"))

    # Date filter: both bounds must be valid, otherwise show all time.
    start = _parse_iso_date(request.args.get("date_from"))
    end = _parse_iso_date(request.args.get("date_to"))
    if start is None or end is None:
        start = end = None
    elif start > end:
        flash("Start date must be before end date.", "error")
        start = end = None

    date_from = start.isoformat() if start else None
    date_to = end.isoformat() if end else None

    presets = _date_presets(date.today())
    active_filter = next(
        (p["key"] for p in presets
         if p["date_from"] == date_from and p["date_to"] == date_to),
        "custom",
    )

    expenses = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    stats = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    categories = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        categories=categories,
        expenses=expenses,
        presets=presets,
        active_filter=active_filter,
        date_from=date_from,
        date_to=date_to,
    )


@app.route("/analytics")
@login_required
def analytics():
    return render_template("analytics.html")


MAX_AMOUNT = 10_000_000  # ₹1,00,00,000
MAX_DESCRIPTION_LENGTH = 200


def _parse_amount(value):
    """Return a positive amount rounded to 2 places, or None if invalid or out of range."""
    try:
        amount = float(value)
    except ValueError:
        return None
    if not math.isfinite(amount) or not 0 < amount <= MAX_AMOUNT:
        return None
    return round(amount, 2)


def _validate_expense_form(form):
    """Return (values, cleaned, error) for a submitted expense form.

    values holds the stripped strings to refill the form. cleaned holds the
    parsed amount, category, ISO date and description ready to save; it is
    None when error (the first validation message) is set.
    """
    values = {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }

    amount = _parse_amount(values["amount"])
    if amount is None:
        return values, None, "Amount must be a number between 0 and ₹1,00,00,000."

    if values["category"] not in CATEGORIES:
        return values, None, "Please choose a valid category."

    expense_date = _parse_iso_date(values["date"])
    if expense_date is None:
        return values, None, "Please enter a valid date."

    if len(values["description"]) > MAX_DESCRIPTION_LENGTH:
        return values, None, (
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )

    cleaned = {
        "amount": amount,
        "category": values["category"],
        "date": expense_date.isoformat(),  # normalised, e.g. 2026-3-5 -> 2026-03-05
        "description": values["description"] or None,
    }
    return values, cleaned, None


def _render_expense_form(form, template="add_expense.html", **context):
    """Render an expense form template, refilled with the given field values."""
    return render_template(
        template,
        categories=CATEGORIES,
        form=form,
        max_description_length=MAX_DESCRIPTION_LENGTH,
        **context,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "GET":
        return _render_expense_form({"date": date.today().isoformat()})

    values, cleaned, error = _validate_expense_form(request.form)
    if error:
        flash(error, "error")
        return _render_expense_form(values)

    insert_expense(
        session["user_id"],
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    )
    flash("Expense added.", "success")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    # 404 for both missing and other users' expenses, so ids aren't leaked.
    expense = get_expense_by_id(id, session["user_id"])
    if expense is None:
        abort(404)

    if request.method == "GET":
        form = {
            "amount": "{:.2f}".format(expense["amount"]),
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }
        return _render_expense_form(form, "edit_expense.html", expense_id=id)

    values, cleaned, error = _validate_expense_form(request.form)
    if error:
        flash(error, "error")
        return _render_expense_form(values, "edit_expense.html", expense_id=id)

    update_expense(
        id,
        session["user_id"],
        cleaned["amount"],
        cleaned["category"],
        cleaned["date"],
        cleaned["description"],
    )
    flash("Expense updated.", "success")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["POST"])
@login_required
def delete_expense(id):
    # 404 for both missing and other users' expenses, so ids aren't leaked.
    if get_expense_by_id(id, session["user_id"]) is None:
        abort(404)

    delete_expense_row(id, session["user_id"])
    flash("Expense deleted.", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
