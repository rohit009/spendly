# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Spendly — a Flask + SQLite expense tracker (INR, "Track every rupee") built as a step-by-step teaching project. Many pieces are intentionally stubbed for "students" to implement in numbered steps; the stub text names the step (e.g. `"Logout — coming in Step 3"`). Keep that step numbering in mind when implementing a feature.

## Commands

A virtualenv lives in `venv/`. Each Bash tool call runs in a fresh shell, so `source venv/bin/activate` doesn't persist — call the venv binaries directly:

```bash
venv/bin/pip install -r requirements.txt   # install deps (flask, pytest, pytest-flask)
venv/bin/python app.py                     # dev server, debug mode, http://localhost:5001
venv/bin/pytest                            # run all tests
venv/bin/pytest tests/test_x.py::test_name # run a single test
```

No tests exist yet; pytest + pytest-flask are the intended framework. No linter is configured.

## Architecture

- `app.py` — the entire app: a single module-level `app = Flask(__name__)` (no app factory, no blueprints). Real routes render templates (`/`, `/register`, `/login`, `/terms`, `/privacy`); `/logout`, `/profile`, and `/expenses/add|<id>/edit|<id>/delete` are placeholder routes returning strings. Auth forms in `login.html`/`register.html` already POST to `/login`/`/register` and render an `error` variable, but the routes currently accept only GET.
- `database/db.py` — empty stub (Step 1). Expected to provide `get_db()` (SQLite connection with `row_factory` and foreign keys enabled), `init_db()` (`CREATE TABLE IF NOT EXISTS`), and `seed_db()`. The DB file `expense_tracker.db` is gitignored.
- `templates/` — Jinja2; every page extends `base.html`, which provides the navbar/footer and blocks `title`, `head` (page-specific CSS), `content`, `scripts` (page-specific JS). Links use `url_for(<endpoint>)`, so renaming a view function breaks templates.
- `static/css/style.css` holds global/shared styles (nav, footer, auth pages, legal pages); `landing.css` is loaded only by `landing.html`. Fonts: DM Serif Display + DM Sans from Google Fonts. `static/js/main.js` is an empty global script; page-specific JS (e.g. the landing YouTube modal) is inline in each template's `scripts` block.

## Conventions

- Currency is INR, never USD: show amounts with `₹` and Indian digit grouping (e.g. `₹1,23,456`), and use rupee amounts in seed data, examples and copy. Don't use `$`.
- Commit messages are prefixed with the area, e.g. `landing: add privacy policy page and route`.
- `exported_promts.md` is an exported chat transcript, not project documentation.
