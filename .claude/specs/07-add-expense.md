# Spec: Add Expense

## Overview
Step 7 lets a logged-in user record a new expense. Until now every expense came
from `seed_db()`, so the profile page could only show demo data. This step
replaces the `"Add expense — coming in Step 7"` placeholder at `/expenses/add`
with a real form (amount, category, date, description) that validates the input
server-side, inserts one row into `expenses` for the current user, and sends
the user back to `/profile` where the new expense appears in the stats,
transaction history and category breakdown. It is the first write path for
expenses, and Steps 8 (edit) and 9 (delete) will reuse its form and validation.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES` list, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4: Profile page UI (`profile.html`, `profile.css`)
- Step 5: Backend connection (profile reads live data via `database/queries.py`)
- Step 6: Date filter (the new expense must respect the profile date filter)

## Routes
- `GET /expenses/add` — show the empty add-expense form; the date field
  defaults to today — logged-in
- `POST /expenses/add` — validate the form, insert the expense for
  `session["user_id"]`, then redirect (302) to `/profile` — logged-in

Both methods redirect unauthenticated users to `/login` (302) and insert
nothing. The view function stays named `add_expense` so existing and future
`url_for('add_expense')` calls keep working.

Validation (on failure, re-render the form with status 200, one inline error
message, and the user's values kept in the fields):
- `amount` — required; a number greater than 0 and no more than 1,00,00,000;
  at most 2 decimal places. Reject `abc`, `0`, `-50`, `12.345`, `nan`, `inf`.
- `category` — required; must be one of `database.db.CATEGORIES`
  (Food, Transport, Bills, Health, Entertainment, Shopping, Other). Any other
  value is rejected, even if crafted outside the form.
- `date` — required; a real zero-padded `YYYY-MM-DD` date, checked with the
  existing `_parse_date()` helper. It may not be in the future.
- `description` — optional; stripped; max 200 characters; stored as `NULL`
  when blank.

## Database changes
No database changes. The existing `expenses` table already has every needed
column (`user_id`, `amount REAL`, `category TEXT`, `date TEXT`,
`description TEXT` nullable, `created_at` default). `user_id` is taken from the
session only, never from the form.

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; a `POST` form
  to `url_for('add_expense')` with:
  - `amount`: `<input type="number" step="0.01" min="0.01">` with a `₹` prefix
  - `category`: `<select>` built from the `categories` list passed by the view,
    with a "Choose a category" placeholder option
  - `date`: `<input type="date">`, default today, `max` set to today
  - `description`: text input, `maxlength="200"`, optional
  - each field with a `<label>`; a "Save expense" submit button and a "Cancel"
    link back to `url_for('profile')`
  - an inline error block (`role="alert"`) shown only when `error` is set
- **Modify:** `templates/profile.html` — add an "Add expense" button linking to
  `url_for('add_expense')` near the transaction history panel heading.
- **Modify:** `templates/base.html` — only if needed for a logged-in "Add
  expense" nav link; keep existing links unchanged.

## Files to change
- `app.py` — replace the `add_expense` placeholder with a GET/POST route;
  import `CATEGORIES`; add a small `_validate_expense(form)` helper that returns
  `(values, error)` so Step 8 can reuse it
- `database/queries.py` — add `create_expense(user_id, amount, category, date,
  description)` in a new marked section (not named `add_expense`, which would
  shadow the view function when imported into `app.py`); one parameterised `INSERT`, opens and
  closes its own connection, returns the new row id
- `templates/profile.html` — "Add expense" button
- `static/css/profile.css` — style for the new button placement, if needed

## Files to create
- `templates/add_expense.html` — the form page
- `static/css/expense_form.css` — form layout styles, loaded through the
  template's `head` block; reusable by the Step 8 edit page
- `tests/test_add_expense.py` — route and helper tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never format values into SQL
- Passwords hashed with werkzeug (no change in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency is INR: show `₹` and Indian digit grouping, never `$`; examples and
  tests use rupee amounts (e.g. ₹450.00, ₹1,850.00)
- Validate everything server-side; the HTML attributes (`min`, `max`,
  `required`, `maxlength`) are a convenience only
- `user_id` comes from the session, never from the request
- Category values must come from `CATEGORIES`; do not duplicate the list in
  the template
- Parse the amount with `decimal.Decimal` (or an equivalent strict check) so
  `nan`, `inf` and more than 2 decimals are rejected; store it rounded to
  2 decimals
- Use Post/Redirect/Get: a successful POST redirects to `/profile` so a page
  refresh does not insert a duplicate
- Keep the helper in `database/queries.py` free of Flask imports
- Leave the Step 8 and Step 9 placeholder routes untouched
- No JavaScript is required for the form

## Definition of done
- [ ] Logged out, visiting `/expenses/add` redirects to `/login`
- [ ] Logged in, `/expenses/add` shows the form with Amount, Category, Date and Description fields, each with a label
- [ ] The Category dropdown lists exactly the 7 categories from `CATEGORIES`
- [ ] The Date field defaults to today
- [ ] Submitting a valid expense (e.g. ₹450.00, Food, today, "Groceries") redirects to `/profile`
- [ ] The new expense appears at the top of the transaction history, formatted as ₹450.00
- [ ] Total spent, transaction count and category breakdown update to include it
- [ ] An expense dated inside an active profile date filter shows up in that filtered view; one dated outside does not
- [ ] Amounts of `0`, `-50`, `abc` or `12.345` show an inline error and nothing is saved
- [ ] A missing or unknown category shows an inline error and nothing is saved
- [ ] A missing, malformed or future date shows an inline error and nothing is saved
- [ ] On a validation error the entered values stay in the form
- [ ] A blank description is accepted and saved as empty
- [ ] Refreshing the profile page after saving does not create a duplicate
- [ ] The new expense belongs only to the logged-in user; other users never see it
- [ ] Profile page has an "Add expense" button that opens the form
- [ ] The form is usable at phone width with no horizontal scroll, and no `$` appears anywhere
- [ ] `venv/bin/python -m pytest` passes, including `tests/test_add_expense.py`
