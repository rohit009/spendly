# Spec: Login and Logout

## Overview
Make `/login` and `/logout` work. The form in `login.html` already POSTs email and password to `/login` and renders an `error` variable, but the route only accepts GET, and `/logout` is a placeholder string. This step verifies credentials against the stored werkzeug hash, remembers the user in Flask's signed `session` cookie, and lets them sign out. It is the second auth step: registration (Step 2) creates users, and every later page (profile, expenses) depends on knowing who is logged in.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `seed_db()` demo user `demo@spendly.com` / `demo123`).
- Step 2 — Registration (users with hashed passwords exist; it redirects to `/login`).

## Routes
- `GET /login` — render the sign-in form; if already logged in, redirect to `/` — public (already exists)
- `POST /login` — validate input, check the credentials, store `user_id` in the session and redirect to `/` (home) on success, re-render the form with an `error` on failure — public
- `GET /logout` — clear the session and redirect to `/` (landing) — public (safe to call when not logged in)
- `GET` and `POST /register` (existing) — if already logged in, redirect to `/` without creating a user — public

View functions stay named `login` and `logout` (templates use `url_for`).

## Database changes
No database changes. The `users` table already has `id`, `email` (UNIQUE) and `password_hash`. Verified against `database/db.py`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — keep the submitted `email` in the input when the form is re-rendered with an error (never re-fill the password)
  - `templates/base.html` — navbar shows "Sign in" / "Get started" when logged out, and "Profile" / "Sign out" (`url_for('profile')`, `url_for('logout')`) when `session.user_id` is set

## Files to change
- `app.py` — import `session`, `check_password_hash`; set `app.secret_key`; accept `GET` and `POST` on `/login`; implement `/logout`
- `templates/login.html` — repopulate `email` on error
- `templates/base.html` — logged-in vs logged-out navbar

## Files to create
- `tests/test_login_logout.py` — pytest tests for the cases in the Definition of done

## New dependencies
No new dependencies (`session` is part of Flask; `check_password_hash` is part of werkzeug).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords checked with werkzeug (`check_password_hash`); never store or log the plain password
- Use CSS variables — never hardcode hex values (reuse existing `.auth-error` styling; no new CSS unless the navbar needs it)
- All templates extend `base.html`
- Do not rename view functions
- `app.secret_key` must come from the `SECRET_KEY` environment variable, with a clearly-labelled dev-only fallback so the app still starts locally; never commit a real secret
- Validation, server-side: email is stripped and lower-cased before lookup; email and password must be non-empty
- Use one generic error for both an unknown email and a wrong password: "Invalid email or password." (do not reveal which one failed)
- Use `get_db()` and always close the connection (`try/finally`)
- Store only `session["user_id"]` (an int) in the session — no password or hash
- On success call `session.clear()` before setting `user_id` to avoid session fixation, then `redirect(url_for("landing"))`
- `/logout` calls `session.clear()` and redirects to `url_for("landing")`
- Do not add a "remember me", password reset, or CSRF tokens (out of scope)
- `/profile` stays a placeholder (Step 4); route protection for it is added then

## Definition of done
- [ ] `GET /login` renders the form (200) when logged out
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/` (home) and sets `session["user_id"]` to the demo user's id
- [ ] Email matching is case- and whitespace-insensitive (`  Demo@Spendly.com ` works)
- [ ] A wrong password and an unknown email both re-render the form (200) with "Invalid email or password." and set no session
- [ ] An empty email or empty password re-renders the form with an error and sets no session
- [ ] After a failed login, the email field keeps its value and the password field is empty
- [ ] `GET /login`, `GET /register` and `POST /register` while logged in redirect to `/` and create no user
- [ ] `GET /logout` clears the session, redirects (302) to `/`, and works when not logged in
- [ ] The navbar shows "Sign in" / "Get started" when logged out and "Profile" / "Sign out" when logged in
- [ ] A user created via `/register` can then log in with the same credentials
- [ ] No SQL string formatting appears in the new code
- [ ] `venv/bin/python -m pytest tests/test_login_logout.py` passes (the `venv/bin/pytest` shebang is currently broken)
- [ ] The app starts with `venv/bin/python app.py` without errors
