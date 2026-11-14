# Spec: Profile Page Design

## Overview
Replace the `/profile` placeholder string with a fully designed profile page for signed-in users. This step is about the **UI only**: the route renders a new `profile.html` template using hardcoded placeholder data defined in the view, shaped exactly like the data later steps will load from the database. The page shows the user's account details, a row of spending summary stats, a category breakdown, and a recent-transactions table. It also introduces the first access control in the app: signed-out visitors who hit `/profile` are sent to `/login`. Wiring the page to real queries is left for the next step, so the design can be reviewed and polished on its own first.

## Depends on
- Step 01 — Database setup (`users` / `expenses` schema and `CATEGORIES`, which the placeholder data mirrors)
- Step 03 — Login and Logout (`session["user_id"]` and `session["user_name"]`, session-aware navbar)

## Routes
- `GET /profile` — render the profile page with placeholder data — logged-in (signed-out visitors are redirected to `url_for('login')`)

No other new routes. `/profile` already exists as a placeholder; it is upgraded, not added.

## Database changes
No database changes. No queries are added in this step: all page data is hardcoded in the view.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; loads `profile.css` via `{% block head %}`. Sections, top to bottom:
    1. **Profile header card** — initials avatar (first letter of each word in the name, max 2), name, email, "Member since <Month YYYY>"
    2. **Summary stats row** — three cards: Total spent (₹), Transactions (count), Top category
    3. **Spending by category** — one row per category: name, horizontal bar sized by share of total, ₹ amount
    4. **Recent transactions** — table with Date, Description, Category (pill), Amount (right-aligned, ₹); an empty state ("No expenses yet") when the list is empty
- **Modify:**
  - `templates/base.html` — when signed in, make the user's name in the navbar a link to `url_for('profile')`

## Files to change
- `app.py` — upgrade `profile()`: redirect to login if `session.get("user_id")` is not set; otherwise build the placeholder `user`, `stats`, `categories` and `expenses` and pass them to `render_template("profile.html", ...)`
- `templates/base.html` — navbar name links to the profile page

## Files to create
- `templates/profile.html`
- `static/css/profile.css`

## New dependencies
No new dependencies. No icon libraries or other CDN scripts: the page uses only the existing fonts and CSS.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (none are needed in this step, and none should be added)
- Passwords hashed with werkzeug (not touched in this step)
- Use CSS variables — never hardcode hex values. Category bar colours must come from existing tokens (`--accent`, `--accent-2`, `--ink-muted`, `--danger`, etc.), not new hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect
- Placeholder data lives in `profile()` in `app.py`, not in the template, with these shapes so the next step only swaps the data source:
  - `user`: `{"name", "email", "member_since"}` — `name` comes from `session["user_name"]`; email and date are placeholders
  - `stats`: `{"total_spent", "transaction_count", "top_category"}`
  - `categories`: list of `{"name", "total", "percent"}`, using names from `CATEGORIES` in `database/db.py`
  - `expenses`: list of `{"date", "description", "category", "amount"}`, dates as `YYYY-MM-DD`, newest first
- Format amounts in the template as rupees with two decimals and thousands separators (e.g. `₹2,200.00`), using `tabular-nums` for numeric columns
- Page styles go in `static/css/profile.css`, scoped with a `.profile-` class prefix; reuse existing tokens (`--radius-*`, `--font-*`, `--paper-card`, `--border`) and match the look of `.auth-card` / `.feature-card`
- Follow the design guidance in `.claude/skills/frontend-design/SKILL.md` for layout and spacing, but the project's own tokens and fonts override its default palette and font suggestions
- Responsive: stats cards stack on narrow screens, and the transactions table scrolls horizontally inside its card instead of overflowing the page
- Use an inline session check in `profile()`; do not add a shared `login_required` decorator yet
- After a successful sign-in, and when a signed-in user visits `/login` or `/register`, redirect to `url_for('profile')` (Step 03 sent them to the landing page). Logout still redirects to the landing page
- Do not touch the expense placeholder routes (`/expenses/...`)

## Definition of done
- [ ] Visiting `/profile` while signed out redirects to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` and visiting `/profile` renders the page without errors
- [ ] The header card shows the signed-in user's name and correct initials (e.g. "DU" for Demo User)
- [ ] Three summary cards show total spent, transaction count and top category, with amounts formatted like `₹2,200.00`
- [ ] The category breakdown shows one bar per category, with bar widths matching each category's share
- [ ] The recent transactions table lists placeholder expenses newest first, with amounts right-aligned
- [ ] Setting `expenses` to an empty list in the view shows the "No expenses yet" empty state instead of an empty table
- [ ] In the navbar, the signed-in user's name links to `/profile`
- [ ] Signing in redirects to `/profile`; visiting `/login` or `/register` while signed in also redirects to `/profile`
- [ ] At phone width (~375px) the stats cards stack and the page has no horizontal scroll
- [ ] `static/css/profile.css` contains no hex colour values
