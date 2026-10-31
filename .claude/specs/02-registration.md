# Spec: Registration

## Overview
Make the existing `/register` page work. The form in `register.html` already POSTs name, email and password to `/register` and renders an `error` variable, but the route only accepts GET. This step validates the submission, rejects duplicate emails, stores the user with a hashed password and sends the visitor to the login page. It is the first auth step and unblocks login/logout (Step 3).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`).

## Routes
- `GET /register` — render the registration form — public (already exists)
- `POST /register` — validate input, create the user, redirect to `/login` on success, re-render the form with an `error` on failure — public

The view function stays named `register` (templates use `url_for`).

## Database changes
No database changes. The `users` table already has `name`, `email` (UNIQUE, NOT NULL), `password_hash` and `created_at`. Verified against `database/db.py`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — keep the submitted `name` and `email` in the inputs when the form is re-rendered with an error (never re-fill the password); no other markup changes

## Files to change
- `app.py` — accept `GET` and `POST` on `/register`; add imports for `request`, `redirect`, `url_for`, `generate_password_hash` and `sqlite3`
- `templates/register.html` — repopulate `name` and `email` on error

## Files to create
- `tests/test_registration.py` — pytest tests for the cases in the Definition of done

## New dependencies
No new dependencies (`werkzeug` and `sqlite3` are already available).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Do not rename view functions
- Validation, all server-side (browser `required` is not enough):
  - name, email and password must be non-empty after stripping whitespace from name and email
  - email must contain `@` and a `.` after it, and is lower-cased before saving and lookup
  - password must be at least 8 characters (matches the form placeholder)
- Duplicate emails: check with a `SELECT` and also catch `sqlite3.IntegrityError` on insert, so a race cannot cause a 500. Show "An account with this email already exists."
- Use `get_db()` and always close the connection (`try/finally` or `with`)
- On success `redirect(url_for("login"))`; do not log the user in (sessions come in Step 3)
- Error messages are rendered through the existing `error` variable; Jinja auto-escapes them

## Definition of done
- [ ] `GET /register` still renders the form (200)
- [ ] Submitting valid name, email and an 8+ character password creates one row in `users` and redirects (302) to `/login`
- [ ] The stored `password_hash` is not the plain password and passes `check_password_hash`
- [ ] Submitting an email that already exists (including `Demo@Spendly.com` vs `demo@spendly.com`) re-renders the form with an error and creates no new row
- [ ] An empty name, an empty email, an email without `@` or a password shorter than 8 characters re-renders the form with a specific error and creates no row
- [ ] After a failed submit, the name and email fields keep their values and the password field is empty
- [ ] No SQL string formatting appears in the new code
- [ ] `venv/bin/pytest tests/test_registration.py` passes
- [ ] The app starts with `venv/bin/python app.py` without errors
