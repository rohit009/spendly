# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly — a Flask + SQLite expense tracker (INR, "Track every rupee"). It is built feature by feature in numbered steps; each step has a spec in `.claude/specs/NN-feature-name.md` (Steps 1–9 are done: database, registration, login/logout, profile page design, profile backend, date filter, add, edit and delete expense). New features continue the numbering, starting with `/create-spec`.

## Commands

A virtualenv lives in `venv/`. Each Bash tool call runs in a fresh shell, so `source venv/bin/activate` doesn't persist — call the venv binaries directly:

```bash
venv/bin/pip install -r requirements.txt   # install deps (flask, werkzeug, pytest, pytest-flask, gunicorn)
venv/bin/python app.py                     # dev server, debug mode, http://localhost:5001
venv/bin/pytest                            # run all tests
venv/bin/pytest tests/test_x.py::test_name # run a single test
```

Tests live in `tests/` (pytest + pytest-flask). Each test file builds its own `client` fixture that points `database.db.DB_PATH` at a temp file, then runs `init_db()` and `seed_db()`, so tests never touch `expense_tracker.db`. Log in as the seeded demo user `demo@spendly.com` / `demo123`. No linter is configured; a hook formats edited Python files with `black`.

## Architecture

- `app.py` — the entire app: a single module-level `app = Flask(__name__)` (no app factory, no blueprints). `init_db()` and `seed_db()` run at import. `SECRET_KEY` comes from the environment (a random key is generated if unset); the session cookie is `SameSite=Lax`.
  - Public routes: `/`, `/register`, `/login`, `/terms`, `/privacy`. `/logout` clears the session.
  - Logged-in routes (redirect to `/login` without `session["user_id"]`): `/profile` (dashboard: summary stats, recent transactions, category breakdown, optional `?from=&to=` date filter), `/analytics` (coming-soon page), `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` (GET shows a confirmation page, POST deletes).
  - Validation lives in helpers: `_parse_date`/`_parse_range` (zero-padded ISO dates), `_parse_amount` (Decimal, max 2 decimals, up to ₹1,00,00,000) and `_validate_expense` (shared by add and edit). Add and edit share the `add_expense.html` template via `_render_expense_form`.
  - Expenses that don't exist and expenses owned by another user both return 404, so ids can't be probed.
  - Jinja filters: `inr` (Indian digit grouping) and `date_label` (e.g. `01 Nov 2026`).
- `database/db.py` — `DB_PATH` (`expense_tracker.db`, gitignored), `CATEGORIES`, `get_db()` (SQLite connection with `row_factory` and foreign keys on), `init_db()` (`CREATE TABLE IF NOT EXISTS` for `users` and `expenses`) and `seed_db()` (demo user plus sample expenses, only when the DB is empty).
- `database/queries.py` — all other SQL, always scoped by `user_id`: `get_user_by_id`, `get_summary_stats`, `get_recent_transactions`, `get_category_breakdown` (all accept `date_from`/`date_to`), `create_expense`, `get_expense`, `update_expense`, `delete_expense_row`.
- `scripts/seed_user.py`, `scripts/seed_expenses.py` — used by the `/seed-user` and `/seed-expense` commands.
- `templates/` — Jinja2; every page extends `base.html`, which provides the navbar/footer and blocks `title`, `head` (page-specific CSS), `content`, `scripts` (page-specific JS). Links use `url_for(<endpoint>)`, so renaming a view function breaks templates.
- `static/css/style.css` holds global/shared styles (nav, footer, auth pages, legal pages); each page has its own stylesheet (`landing.css`, `profile.css`, `expense_form.css`, `delete_expense.css`, `analytics.css`) loaded in its `head` block. Fonts: DM Serif Display + DM Sans from Google Fonts. Page-specific JS (e.g. the landing YouTube modal) is inline in each template's `scripts` block.
- Deployment: `Procfile` runs gunicorn (`app:app`) on Railway. Set `SECRET_KEY` in production; `FLASK_DEBUG=0` turns off debug mode for `python app.py`.

## Claude Code setup (`.claude/`)

- `specs/` — one spec per step, written before the code.
- `commands/` — `/create-spec` (spec + feature branch), `/test-feature`, `/code-review-feature`, `/seed-user`, `/seed-expense`.
- `agents/` — `spendly-test-writer` (tests from the spec, not the implementation), `spendly-test-runner`, and `spendly-security-reviewer` + `spendly-quality-reviewer` (run in parallel on the diff).
- `skills/` — `frontend-design` (use before writing templates or CSS) and `ship-feature` (commit, PR, merge, back to `main`).
- `settings.json` — hooks: `black` after every Python edit; destructive shell commands on `expense_tracker.db`, `.env` or `migrations/` are blocked.

## Conventions

- Currency is INR, never USD: show amounts with `₹` and Indian digit grouping (e.g. `₹1,23,456`), and use rupee amounts in seed data, examples and copy. Don't use `$`.
- Commit messages are prefixed with the area, e.g. `landing: add privacy policy page and route`.
- Each feature goes on its own branch and is merged into `main` through a pull request.
