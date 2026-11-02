# Spec: Date Filter for Profile Page

## Overview
Step 6 lets a logged-in user narrow the profile page to a date range. A small
"From / To" form above the stats sends `from` and `to` as query parameters to
`GET /profile`. The same range then applies to all three data sections at once:
the summary stats, the transaction history and the category breakdown, so the
numbers on the page always describe the same set of expenses. With no filter the
page behaves exactly as it does after Step 5. This builds directly on the
`database/queries.py` helpers from Step 5, which gain optional date arguments.

## Depends on
- Step 1: Database setup (`expenses.date` stored as ISO `YYYY-MM-DD` text)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 4: Profile page UI (`profile.html`, `profile.css`)
- Step 5: Backend connection (`database/queries.py` helpers feed the page)

## Routes
No new routes. The existing `GET /profile` — logged-in — accepts two optional
query parameters:
- `from` — start date, inclusive, `YYYY-MM-DD`
- `to` — end date, inclusive, `YYYY-MM-DD`

Either one may be given alone (open-ended range). Examples:
`/profile?from=2026-11-01&to=2026-11-30`, `/profile?from=2026-11-15`.

Behaviour for bad input:
- A value that is not a real `YYYY-MM-DD` date, or `from` later than `to`: show
  one inline error message ("Enter valid dates, with From on or before To."),
  and show the unfiltered page data. Never raise a 400 or 500.
- Blank values are treated as "not set".
- Unauthenticated requests still redirect to `/login` (302), and the filter
  parameters are not preserved.

## Database changes
No database changes. `expenses.date` is `TEXT NOT NULL` in ISO format, so
`date >= ?` and `date <= ?` compare correctly as strings. No index is needed at
this size.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter form above the stat row: a `GET` form to `url_for('profile')`
    with two `<input type="date">` fields (`name="from"`, `name="to"`), each with
    a `<label>`, pre-filled with the values in effect, an "Apply" button and a
    "Clear" link back to `url_for('profile')`.
  - Show the inline error above the form when the dates were invalid.
  - When a filter is active, show a line such as "Showing 01 Nov 2026 to
    30 Nov 2026" near the form.
  - Empty states: with a filter active the transaction panel says "No
    transactions in this date range." and the breakdown panel says "Nothing to
    break down in this date range." Without a filter, the Step 5 messages stay.
  - Keep every amount going through the `inr` filter.
- **Modify:** `static/css/profile.css` — styles for the filter form, using the
  existing CSS variables only, with the fields wrapping on mobile.

## Files to change
- `app.py` — `profile()` reads and validates `from` / `to`, passes them to the
  helpers, and passes `date_from`, `date_to`, `filter_active` and `filter_error`
  to the template
- `database/queries.py` — `get_summary_stats`, `get_recent_transactions` and
  `get_category_breakdown` take optional `date_from=None, date_to=None`
- `templates/profile.html` — filter form, messages and empty states
- `static/css/profile.css` — filter form styles
- `tests/test_backend_connection.py` — keep passing (the new arguments are optional)

## Files to create
- `tests/test_date_filter.py` — unit and route tests for the filter

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only. Build the optional `AND date >= ?` / `AND date <= ?`
  clauses from fixed strings and append the values to the parameter list. Never
  format a date into the SQL.
- Passwords hashed with werkzeug (no change in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency is INR: always `₹` with Indian grouping, never `$`
- Validate dates in `app.py` with `datetime.strptime(value, "%Y-%m-%d")`. The
  query helpers can then trust their input.
- The range is inclusive at both ends.
- Every query stays scoped by `WHERE user_id = ?`. The filter must never widen
  the data a user can see.
- Percentages in the filtered breakdown still sum to 100, based on the filtered
  total, and the empty-range results are zeros and an empty list, as in Step 5.
- The transaction list keeps its limit of 10, newest first, applied after
  filtering.
- The filter is a plain GET form. No JavaScript is required.
- Do not use today's date inside the helpers; tests must not depend on the
  current day.

## Tests to write

### Unit tests
File: `tests/test_date_filter.py`. Use a temporary DB and a fixed set of
expenses with explicit dates across at least three months.

| Function | Input | Expected output |
|---|---|---|
| `get_summary_stats` | range covering part of the data | totals, count and top category from that range only |
| `get_summary_stats` | range with no expenses | `{"total_spent": 0, "transaction_count": 0, "top_category": "—"}` |
| `get_recent_transactions` | `date_from` only | only rows on or after it, newest first |
| `get_recent_transactions` | `date_to` only | only rows on or before it |
| `get_recent_transactions` | both ends equal one day | only that day's rows (inclusive boundaries) |
| `get_category_breakdown` | filtered range | amounts from that range only; `pct` sums to 100 |
| `get_category_breakdown` | empty range | `[]` |
| all three | no date arguments | same results as Step 5 |
| all three | another user's expenses inside the range | never included |

### Route tests
`GET /profile?from=...&to=...`:
- Unauthenticated: 302 to `/login`
- Valid range: 200, with the stats, rows and categories matching that range
- Only `from`, or only `to`: 200 and filtered
- Boundary dates are included
- Range with no expenses: 200, ₹0.00, 0 transactions, the filtered empty-state
  messages
- Form inputs are pre-filled with the submitted dates
- `from` later than `to`: 200, the error message, unfiltered data
- Garbage values (`from=abc`, `to=2026-13-45`): 200, the error message, no 500
- Blank `from=&to=`: 200, treated as no filter, no error
- SQL-injection-looking value (`from=' OR 1=1 --`): 200, handled as invalid
- No `$` anywhere in the response

## Definition of done
- [ ] `/profile` shows a From / To date form above the stats, with Apply and Clear
- [ ] Choosing a range changes the total spent, transaction count, top category,
      transaction rows and category breakdown together, and all of them use the same range
- [ ] Both ends of the range are inclusive (an expense on the From or To date is counted)
- [ ] Giving only From, or only To, works
- [ ] The date fields stay filled with the chosen dates after Apply
- [ ] Clear returns to the full, unfiltered profile
- [ ] A range with no expenses shows ₹0.00, 0 transactions and the "in this date range" empty messages, with no errors
- [ ] From later than To, or a malformed date, shows the inline error and the unfiltered data, never a 500
- [ ] Category percentages still add up to 100 % within a filtered range
- [ ] Another user's expenses never appear, whatever the filter
- [ ] Opening `/profile` with no parameters looks and behaves exactly as before
- [ ] All amounts show ₹, and the form is usable at phone width with no horizontal scroll
- [ ] `venv/bin/python -m pytest` passes, including `tests/test_date_filter.py`
