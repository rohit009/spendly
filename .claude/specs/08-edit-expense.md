# Spec: Edit Expense

## Overview
Step 8 lets a logged-in user change an expense they already recorded. Today the
`/expenses/<id>/edit` route is a placeholder returning
`"Edit expense — coming in Step 8"`, so a typo in an amount, category or date
can only be fixed by editing the database by hand. This step replaces the
placeholder with a pre-filled form that reuses the Step 7 validation helper
(`_validate_expense`), form renderer and form stylesheet, updates the single
matching row, and sends the user back to `/profile`. Because the profile page
currently shows transactions without an id, it also adds an "Edit" link per
row. Ownership is enforced: a user can only edit their own expenses.

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES`, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Backend connection (`database/queries.py`)
- Step 6: Date filter (an edited expense must respect the profile filter)
- Step 7: Add expense (`_validate_expense`, `_render_expense_form`,
  `add_expense.html`, `expense_form.css`)

## Routes
- `GET /expenses/<int:id>/edit` — show the form pre-filled with the expense's
  current amount, category, date and description — logged-in (owner only)
- `POST /expenses/<int:id>/edit` — validate, update the row, then redirect
  (302) to `/profile` — logged-in (owner only)

Behaviour:
- Unauthenticated users are redirected to `/login` (302); nothing is changed.
- If the expense does not exist **or belongs to another user**, return 404 with
  the same response for both cases, so ids of other users' expenses can't be
  probed. Nothing is changed.
- Validation is identical to Step 7 (amount > 0, ≤ 1,00,00,000, max 2
  decimals; category in `CATEGORIES`; real non-future `YYYY-MM-DD` date;
  description ≤ 200 chars, blank stored as `NULL`). On failure re-render the
  form with status 200, one inline error, and the user's typed values kept.
- The view function stays named `edit_expense`. The Step 9 delete placeholder
  is untouched.

## Database changes
No database changes. The existing `expenses` table has every needed column.
`user_id` and `created_at` are never modified by an edit, and `user_id` is
taken from the session only, never from the form.

## Templates
- **Create:** none. The edit page reuses `templates/add_expense.html`.
- **Modify:** `templates/add_expense.html` — make it work for both modes:
  - the page title, heading and subtitle switch between "Add" and "Edit" copy
  - the form `action` is passed in by the view (`url_for('add_expense')` or
    `url_for('edit_expense', id=id)`) instead of being hardcoded
  - the submit button reads "Save expense" (add) or "Save changes" (edit)
- **Modify:** `templates/profile.html` — add an "Actions" column to the
  transaction table with an "Edit" link per row to
  `url_for('edit_expense', id=t.id)`; the link has an accessible label such
  as `aria-label="Edit expense: {{ t.description or t.category }}"`.

## Files to change
- `app.py` — replace the `edit_expense` placeholder with a GET/POST route;
  extend `_render_expense_form` to take the mode (heading, form action,
  button label); import `get_expense` and `update_expense`
- `database/queries.py` — in a new marked section add:
  - `get_expense(user_id, expense_id)` — returns the row as a dict or `None`
    when missing or not owned by `user_id`
  - `update_expense(user_id, expense_id, amount, category, date, description)`
    — returns `True` if a row was updated, `False` otherwise
  - extend `get_recent_transactions` to include `id` in each dict
- `templates/add_expense.html` — dual-mode copy and form action
- `templates/profile.html` — Edit link column
- `static/css/profile.css` — style the Edit link/column (use CSS variables)
- `static/css/expense_form.css` — only if edit mode needs a style tweak

## Files to create
- `tests/test_edit_expense.py` — route and query-helper tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never format values into SQL
- Passwords hashed with werkzeug (no change in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency is INR: show `₹` with Indian digit grouping, never `$`; examples
  and tests use rupee amounts (e.g. ₹450.00, ₹1,850.00)
- The UPDATE must filter on both `id` and `user_id`
  (`WHERE id = ? AND user_id = ?`) so ownership is enforced in SQL, not just
  in the view
- Reuse `_validate_expense` and `_render_expense_form`; do not duplicate
  validation or the category list
- Use Post/Redirect/Get: a successful POST redirects to `/profile`
- Validate everything server-side; HTML attributes are convenience only
- Keep helpers in `database/queries.py` free of Flask imports; open and close
  their own connection
- Do not change `created_at`; do not implement delete (Step 9)
- No JavaScript is required

## Definition of done
- [ ] Logged out, visiting `/expenses/<id>/edit` (GET or POST) redirects to `/login`
- [ ] Each row in the profile transaction table has an "Edit" link that opens the edit form
- [ ] The edit form is pre-filled with that expense's amount, category, date and description
- [ ] The heading and button say "Edit"/"Save changes", not "Add"
- [ ] Changing the amount and saving redirects to `/profile` and shows the new amount formatted as ₹ with Indian grouping (e.g. ₹1,850.00)
- [ ] Changing the category and date updates the row, the category breakdown and the stats totals
- [ ] An edit that moves an expense into or out of an active profile date filter is reflected in the filtered view
- [ ] Clearing the description saves successfully and the row shows an empty description
- [ ] Amounts of `0`, `-50`, `abc` or `12.345` show an inline error, keep the typed values, and change nothing
- [ ] An unknown category, or a missing, malformed or future date shows an inline error and changes nothing
- [ ] Requesting another user's expense id (GET or POST) returns 404 and changes nothing
- [ ] Requesting a non-existent expense id returns 404
- [ ] Saving an edit does not create a new row or change `created_at` / `user_id`
- [ ] Refreshing the profile page after saving does not re-submit the edit
- [ ] Cancel returns to `/profile` without saving
- [ ] The add-expense page at `/expenses/add` still works unchanged
- [ ] The form and the new Edit column are usable at phone width with no horizontal page scroll, and no `$` appears anywhere
- [ ] `venv/bin/python -m pytest` passes, including `tests/test_edit_expense.py`
