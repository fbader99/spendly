import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import CATEGORIES, create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"  # dev only; needed for flash()

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
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Placeholder data for the page design. The next step replaces these
    # hardcoded values with real queries; the shapes stay the same.
    user = {
        "name": session["user_name"],
        "email": "demo@spendly.com",
        "member_since": "November 2026",
    }

    expenses = [
        {"date": "2026-11-01", "description": "Groceries for the week", "category": "Food", "amount": 450.0},
        {"date": "2026-11-03", "description": "Auto rickshaw to office", "category": "Transport", "amount": 120.0},
        {"date": "2026-11-05", "description": "Electricity bill", "category": "Bills", "amount": 2200.0},
        {"date": "2026-11-07", "description": "Pharmacy - vitamins", "category": "Health", "amount": 650.0},
        {"date": "2026-11-08", "description": "Movie tickets", "category": "Entertainment", "amount": 499.0},
        {"date": "2026-11-10", "description": "New running shoes", "category": "Shopping", "amount": 1599.0},
        {"date": "2026-11-12", "description": "Gift wrapping", "category": "Other", "amount": 300.0},
        {"date": "2026-11-14", "description": "Dinner with friends", "category": "Food", "amount": 280.0},
    ]
    expenses = sorted(expenses, key=lambda e: e["date"], reverse=True)

    # Derive the summary from the expenses so the numbers always agree.
    total_spent = sum(e["amount"] for e in expenses)
    totals = {name: 0.0 for name in CATEGORIES}
    for e in expenses:
        totals[e["category"]] += e["amount"]

    categories = sorted(
        (
            {"name": name, "total": total, "percent": round(total / total_spent * 100)}
            for name, total in totals.items()
            if total > 0
        ),
        key=lambda c: c["total"],
        reverse=True,
    )

    stats = {
        "total_spent": total_spent,
        "transaction_count": len(expenses),
        "top_category": categories[0]["name"] if categories else None,
    }

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        categories=categories,
        expenses=expenses,
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
