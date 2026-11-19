# Spec: Delete Expense

## Overview
Step 9 lets a logged-in user permanently remove an expense they recorded. Today
`/expenses/<id>/delete` is a placeholder returning
`"Delete expense — coming in Step 9"`. This step replaces it with a two-stage
flow that needs no JavaScript: `GET` shows a confirmation page describing the
expense (amount, category, date, description) with a "Delete" button and a
"Cancel" link, and `POST` performs the deletion and redirects to `/profile`
with a one-time "Expense deleted" banner (the same flash mechanism added in
Step 8). Deleting never happens on GET, so links, prefetching or crawlers can't
destroy data. Each row on the profile table gets a "Delete" link beside "Edit".
Ownership is enforced: a user can only delete their own expenses.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Backend connection (`database/queries.py`)
- Step 6: Date filter (a deleted expense must disappear from filtered views,
  stats and the category breakdown)
- Step 8: Edit expense (`get_expense`, the flash banner, the Actions column,
  `.link-edit` styling)

## Routes
- `GET /expenses/<int:id>/delete` — show a confirmation page for the expense —
  logged-in (owner only)
- `POST /expenses/<int:id>/delete` — delete the row, flash "Expense deleted",
  redirect (302) to `/profile` — logged-in (owner only)

Behaviour:
- Unauthenticated users are redirected to `/login` (302) on GET and POST;
  nothing is changed.
- If the expense does not exist **or belongs to another user**, return 404 with
  the same response for both cases, so ids can't be probed. Nothing is changed.
- GET never modifies data.
- POSTing to an id that was already deleted returns 404 (no error page, no
  second flash).
- The view function stays named `delete_expense`.

## Database changes
No database changes. Deletion is a hard `DELETE` of one row from `expenses`;
no other table references expenses.

## Templates
- **Create:** `templates/delete_expense.html` — confirmation page extending
  `base.html`: heading "Delete expense?", a summary of the expense (amount as
  `₹` with Indian grouping via the `inr` filter, category, formatted date,
  description or "—"), a `<form method="post">` with a "Delete" button, and a
  "Cancel" link back to `/profile`.
- **Modify:** `templates/profile.html` — add a "Delete" link next to "Edit" in
  each row's actions cell, with
  `aria-label="Delete expense: {{ t.description or t.category }}"`.

## Files to change
- `app.py` — replace the `delete_expense` placeholder with a GET/POST route;
  import `delete_expense` helper under a non-clashing name (e.g.
  `delete_expense as remove_expense`) or name the helper
  `delete_expense_row` to avoid shadowing the view
- `database/queries.py` — new `# === SECTION 6: DELETE EXPENSE (Step 9) ===`
  with `delete_expense_row(user_id, expense_id)` returning `True` if a row was
  deleted, `False` otherwise
- `templates/profile.html` — Delete link
- `static/css/profile.css` — style `.link-delete` (use CSS variables; a danger
  colour variable if one exists in `style.css`, otherwise add one to `:root`
  rather than hardcoding hex)
- `static/css/expense_form.css` — only if the confirmation page needs shared
  form/button styles

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css` — only if styles don't fit existing sheets
- `tests/test_delete_expense.py` — route and query-helper tests

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never format values into SQL
- Passwords hashed with werkzeug (no change in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency is INR: show `₹` with Indian digit grouping, never `$`; tests use
  rupee amounts
- The DELETE must filter on both `id` and `user_id`
  (`WHERE id = ? AND user_id = ?`) so ownership is enforced in SQL, not just
  in the view
- Deletion happens on POST only; GET must be side-effect free
- Use Post/Redirect/Get: a successful POST redirects to `/profile`
- `user_id` comes from the session only, never from the form
- Keep helpers in `database/queries.py` free of Flask imports; open and close
  their own connection
- Reuse the existing flash banner markup in `profile.html`; do not duplicate it
- No JavaScript is required (no `confirm()` dialogs; the confirmation page is
  the safeguard)

## Definition of done
- [ ] Logged out, visiting `/expenses/<id>/delete` (GET or POST) redirects to `/login` and deletes nothing
- [ ] Each profile row has a "Delete" link that opens the confirmation page
- [ ] The confirmation page shows that expense's amount (₹, Indian grouping), category, date and description
- [ ] Opening the confirmation page (GET) does not delete anything; refreshing it is harmless
- [ ] "Cancel" returns to `/profile` and the expense is still there
- [ ] Clicking "Delete" removes the row, redirects to `/profile`, and shows "Expense deleted" once at the top
- [ ] Refreshing `/profile` after deleting does not show the banner again or re-submit anything
- [ ] The deleted expense disappears from the table, the stats totals and the category breakdown
- [ ] Deleting an expense inside an active date filter updates the filtered view
- [ ] Deleting the last expense shows the empty state ("No transactions yet." / "No transactions in this date range.")
- [ ] Requesting another user's expense id (GET or POST) returns 404 and deletes nothing
- [ ] Requesting a non-existent or already-deleted id returns 404
- [ ] Only the targeted row is removed; other expenses and users are untouched
- [ ] The Edit link and edit flow from Step 8 still work unchanged
- [ ] The confirmation page and the actions column are usable at phone width with no horizontal page scroll, and no `$` appears anywhere
- [ ] `venv/bin/python -m pytest` passes, including `tests/test_delete_expense.py`
