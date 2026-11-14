# Spec: Login and Logout

## Overview
Let registered users sign in to and out of Spendly. This step upgrades the GET-only `/login` stub into a working form handler that looks up the user by email, verifies the password hash with Werkzeug, and stores the user's id and name in Flask's `session`. It also replaces the `/logout` placeholder with a route that clears the session. The navbar in `base.html` becomes session-aware, showing "Sign in / Get started" to visitors and the user's name with a "Sign out" link to logged-in users. This is the authentication foundation that the profile page (Step 4) and all expense features build on.

## Depends on
- Step 01 — Database setup (`users` table, `get_db()`, seeded demo user `demo@spendly.com` / `demo123`)
- Step 02 — Registration (`create_user()`, `app.secret_key`, flash messages on the login page)

## Routes
- `GET /login` — render the sign-in form — public (already exists, keep it)
- `POST /login` — validate credentials, set `session["user_id"]` and `session["user_name"]`, redirect to `url_for('landing')` — public
- `GET /logout` — clear the session and redirect to `url_for('landing')` (no flash: the landing page has no flash block) — logged-in (harmless if called while logged out)

## Database changes
No database changes. The existing `users` table (id, name, email, password_hash, created_at) is sufficient.

A new DB helper must be added to `database/db.py`:
- `get_user_by_email(email)` — returns the matching `users` row (`sqlite3.Row`) or `None`. Uses a parameterised `SELECT`.

## Templates
- **Create:** None
- **Modify:**
  - `templates/login.html`
    - Change form `action` to `{{ url_for('login') }}` (no hardcoded URL)
    - Re-populate the email field with `value="{{ email or '' }}"` after a failed attempt
    - Keep the existing flash block and visual design
  - `templates/base.html`
    - Navbar: if `session.user_id` is set, show the user's name (`session.user_name`) and a "Sign out" link to `url_for('logout')`; otherwise show the existing "Sign in" and "Get started" links

## Files to change
- `app.py` — import `session` and `check_password_hash`; upgrade `login()` to handle GET and POST; implement `logout()`
- `database/db.py` — add `get_user_by_email()`
- `templates/login.html` — `url_for` form action and sticky email value
- `templates/base.html` — session-aware navbar links

## Files to create
None.

## New dependencies
No new dependencies. Uses Flask's built-in `session` and `werkzeug.security.check_password_hash` (already installed).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never use f-strings or string formatting in SQL
- Passwords hashed with werkzeug — verify with `check_password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use `url_for()` for every internal link and redirect — never hardcode URLs
- Normalise the submitted email with `.strip().lower()` to match how registration stores it
- Server-side validation for `POST /login`:
  1. Both email and password are non-empty → otherwise flash "Email and password are required."
  2. User exists and password matches → otherwise flash a single generic "Invalid email or password." (do not reveal which one was wrong)
- On failure, re-render `login.html` with the flashed error and the submitted email — do not redirect
- On success, call `session.clear()` before setting `session["user_id"]` and `session["user_name"]` (avoids carrying over stale session data)
- `logout()` must use `session.clear()` and redirect; it must not render a template
- `login()` and `register()` must redirect a signed-in user (`session.get("user_id")` set) to `url_for('landing')` for both GET and POST
- Do not build the profile page or a `login_required` decorator — those belong to Step 4
- Do not touch the other placeholder routes (`/profile`, `/expenses/...`)

## Definition of done
- [ ] `GET /login` renders the sign-in form without errors
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects to `/` (the landing page, with the user's name in the navbar)
- [ ] Signing in with an email in mixed case or with surrounding spaces (e.g. ` Demo@Spendly.com `) still succeeds
- [ ] A wrong password re-renders the login form with "Invalid email or password." and keeps the email filled in
- [ ] An unregistered email shows the same "Invalid email or password." message
- [ ] Submitting with an empty field shows "Email and password are required."
- [ ] A user created via `/register` can sign in with the password they chose
- [ ] After sign-in, the navbar shows the user's name and a "Sign out" link instead of "Sign in / Get started"
- [ ] Clicking "Sign out" redirects to the landing page and the navbar reverts to "Sign in / Get started"
- [ ] Visiting `/logout` while not signed in redirects to the landing page without errors
- [ ] Visiting `/login` or `/register` while signed in redirects to the landing page
