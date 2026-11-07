# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly is a Flask expense tracker built as a step-by-step teaching project. Much of the app is deliberately unfinished: placeholder routes and stub files are labelled with the step that will implement them ("coming in Step N", "Students will write this file in Step 1"). When building a feature, follow the step's scope and don't fill in later steps unless asked.

## Commands

The venv lives in `venv/` (Python 3.9). Each shell command runs in a fresh shell, so call the venv binaries directly instead of relying on `source venv/bin/activate`.

```bash
venv/bin/pip install -r requirements.txt   # install deps (Flask, Werkzeug, pytest, pytest-flask)
venv/bin/python app.py                     # dev server at http://127.0.0.1:5001, debug + auto-reload
venv/bin/pytest                            # run tests (no tests exist yet)
venv/bin/pytest tests/test_x.py::test_name # run a single test
```

There is no linter or build step configured.

## Architecture

- **`app.py`**: the whole Flask app with every route defined on one `app` object (no blueprints yet). Real routes render templates: `/`, `/register`, `/login`, `/terms`, `/privacy`. Placeholder routes return strings: `/logout`, `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete`. Templates link to pages with `url_for('<function name>')`, so renaming a view function breaks links.
- **`database/db.py`**: plain `sqlite3` (no ORM) with `get_db()` (a connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS` for `users` and `expenses`) and `seed_db()` (a demo user and 8 sample expenses, skipped if users already exist). `app.py` calls `init_db()` and `seed_db()` at startup. The DB file `spendly.db` in the project root is gitignored. Hash passwords with `method="pbkdf2:sha256"`: the venv's Python 3.9 has no `hashlib.scrypt`, which is Werkzeug's default.
- **Templates**: every page extends `templates/base.html`, which provides the navbar, footer, `style.css`, `main.js` and the blocks `title`, `head`, `content` and `scripts`. Pages add their own CSS through `{% block head %}` (for example, `landing.html` loads `landing.css`) and page-specific JS inline through `{% block scripts %}` (for example, the landing page's YouTube modal).
- **Auth forms**: `login.html` and `register.html` already POST to `/login` and `/register` and show an `{{ error }}` variable, but the routes only handle GET so far.
- **Styling**: `static/css/style.css` defines the design tokens as CSS variables on `:root` (`--ink*`, `--paper*`, `--accent`, `--accent-2`, `--danger`, `--border`) and the shared components. Use these tokens rather than hard-coded colours. The fonts are DM Serif Display and DM Sans from Google Fonts. Currency copy uses rupees.
- **`static/js/main.js`**: an empty placeholder for shared JS.

## Conventions

- Commit messages use a short area prefix, like `landing: add privacy policy page and route`.
- `file.md` is a saved transcript of an earlier Claude Code session, not project documentation.
