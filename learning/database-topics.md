# Database topics for Spendly

Spendly stores everything in one SQLite file (`expense_tracker.db`) through Python's built-in `sqlite3` module, with no ORM. This guide lists only the database ideas the project actually uses. Line numbers refer to the current code, so they may drift.

Files to keep open: `database/db.py`, `database/queries.py`, `app.py` (register/login), `scripts/seed_user.py`, `scripts/seed_expenses.py`, `tests/test_backend_connection.py`.

## Suggested learning order

1. Relational basics, primary keys, the two tables
2. The `sqlite3` module: connect, execute, fetch, commit, close
3. Parameterised queries and SQL injection
4. Constraints, `IntegrityError`, foreign keys
5. SELECT / WHERE / ORDER BY / LIMIT
6. Aggregates, `GROUP BY`, per-user scoping
7. Transactions, `executemany`, seeding and idempotence
8. Money and date storage choices
9. Testing against a temp DB

---

## 1. Relational basics: tables, rows, primary key, AUTOINCREMENT

**What:** A table is a grid of rows (records) and typed columns. A primary key uniquely identifies a row. `INTEGER PRIMARY KEY AUTOINCREMENT` makes SQLite assign 1, 2, 3... and never reuse an id.

**Where:** `database/db.py:37` (users.id), `:45` (expenses.id).

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT,
```

**Practice:** Why must `id` be a primary key rather than `email` or `name`?

## 2. The schema and the one-to-many relationship

**What:** `users` (id, name, email, password_hash, created_at) and `expenses` (id, user_id, amount, category, date, description, created_at). One user has many expenses; each expense belongs to exactly one user via `expenses.user_id`.

**Where:** `database/db.py:36-52`.

```sql
user_id INTEGER NOT NULL REFERENCES users(id),
```

**Practice:** Draw the two tables. Which column links them, and on which side is the "many"?

## 3. Foreign keys and `PRAGMA foreign_keys = ON`

**What:** A foreign key says "this value must exist in another table". SQLite parses `REFERENCES` but does NOT enforce it unless you run the pragma on every new connection.

**Where:** `database/db.py:27` (inside `get_db()`, so every connection gets it).

```python
conn.execute("PRAGMA foreign_keys = ON")
```

**Practice:** In the sqlite3 shell, try `INSERT INTO expenses(user_id,amount,category,date) VALUES (9999, 100, 'Food', '2026-01-01');` with and without the pragma. What differs?

## 4. NOT NULL, UNIQUE and `IntegrityError`

**What:** `NOT NULL` rejects missing values; `UNIQUE` rejects duplicates (here, two accounts with the same email). Violations raise `sqlite3.IntegrityError`. Register checks first with a SELECT (friendly path), then still catches the error to survive a race between two requests.

**Where:** `database/db.py:39` (UNIQUE), `app.py:58` (pre-check), `app.py:66` (catch).

```python
except sqlite3.IntegrityError:
    return fail(duplicate)
```

**Practice:** Why keep the `except` when the SELECT pre-check already exists?

## 5. `CREATE TABLE IF NOT EXISTS` and `executescript`

**What:** `IF NOT EXISTS` makes table creation safe to repeat (idempotent), so the app can call `init_db()` on every start. `executescript` runs several `;`-separated statements in one call (it takes no parameters).

**Where:** `database/db.py:31-56`, called at startup from `app.py:20`.

```python
conn.executescript("""CREATE TABLE IF NOT EXISTS users (...); CREATE TABLE IF NOT EXISTS expenses (...);""")
```

**Practice:** Add a nullable `notes TEXT` column to the CREATE statement. Why will an existing `.db` file NOT gain it? (See "not in the project yet": migrations.)

## 6. The `sqlite3` module lifecycle

**What:** `connect(path)` opens the file; `execute(sql, params)` runs a statement and returns a cursor; `fetchone()` returns one row or `None`, `fetchall()` a list; `commit()` saves writes; `close()` releases the file. `row_factory = sqlite3.Row` lets you read columns by name (`row["name"]`) instead of by index.

**Where:** `database/db.py:23-28` (`get_db`), `database/queries.py:16-22` (open, query, close in `try/finally`), `database/queries.py:25` (`row is None` check).

```python
conn = get_db()
try:
    row = conn.execute("SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
finally:
    conn.close()
```

**Practice:** What does `fetchone()` return when nothing matches, and what would break in `get_user_by_id` if it returned `[]` instead?

## 7. `lastrowid`

**What:** After an INSERT, `cursor.lastrowid` is the new row's auto-generated id.

**Where:** `database/db.py:70` (seed gets the demo user's id to attach expenses), `scripts/seed_user.py:33`, `tests/test_backend_connection.py:31`.

```python
cursor = conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", (...))
user_id = cursor.lastrowid
```

**Practice:** Why is `lastrowid` needed before inserting the demo user's expenses?

## 8. Parameterised queries and SQL injection

**What:** Always pass values through `?` placeholders. The driver sends SQL and data separately, so user input can never change the query's structure. Building SQL by string formatting lets an attacker inject SQL.

Safe (what the project does everywhere, e.g. `app.py:94-97`):

```python
conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
```

Unsafe, do NOT do this:

```python
# WHAT NOT TO DO: string-built SQL
conn.execute(f"SELECT id FROM users WHERE email = '{email}'")
# email = "x' OR '1'='1" turns it into: ... WHERE email = 'x' OR '1'='1'  (matches every user)
```

Note: a single-value tuple needs the trailing comma: `(email,)`. Placeholders work for values only, not table or column names.

**Practice:** What does the unsafe query return if `email` is `' OR 1=1 --`? Rewrite it safely.

## 9. SELECT, WHERE, ORDER BY, LIMIT

**What:** SELECT picks columns, WHERE filters rows, ORDER BY sorts (`DESC` = newest/biggest first, second key breaks ties), LIMIT caps the row count. `SELECT 1 ... fetchone()` is a cheap "does it exist?" test.

**Where:** `database/queries.py:41-44`, `app.py:58`, `scripts/seed_user.py:24`.

```sql
SELECT date, description, category, amount FROM expenses
WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT ?
```

**Practice:** Why add `id DESC` as a tiebreaker after `date DESC`?

## 10. Aggregates: `SUM`, `COUNT`, `COALESCE`

**What:** Aggregates collapse many rows into one value. `SUM` of zero rows is `NULL`, so `COALESCE(x, 0)` substitutes 0. `AS total` names the output column.

**Where:** `database/queries.py:66-70`, `database/db.py:62` (`COUNT(*)` on users).

```sql
SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt FROM expenses WHERE user_id = ?
```

**Practice:** For a user with no expenses, what do `SUM(amount)` and `COUNT(*)` return without COALESCE?

## 11. `GROUP BY`

**What:** Splits rows into buckets (one per category) and applies aggregates per bucket. Combined with `ORDER BY SUM(...) DESC LIMIT 1` it finds the top category.

**Where:** `database/queries.py:71-74` (top category), `:93-97` (full breakdown).

```sql
SELECT category, SUM(amount) AS total FROM expenses
WHERE user_id = ? GROUP BY category ORDER BY total DESC, category ASC
```

**Practice:** Change it to `COUNT(*)` per category. What does the result mean?

## 12. Per-user scoping with `WHERE user_id = ?`

**What:** Every expense query filters by the logged-in user's id, so one user can never see another's data. Forgetting this clause is a data leak, not a crash.

**Where:** every query in `database/queries.py` (lines 19, 43, 68, 72, 95); proven by `tests/test_backend_connection.py:142-147` and `:184-190`.

**Practice:** Write a query for the total spent by user 2 on "Food". Which two WHERE conditions are needed?

## 13. Transactions: commit, rollback, `with conn`

**What:** A transaction groups writes so they all succeed or none do. Python's sqlite3 opens one implicitly before INSERT/UPDATE/DELETE; changes are invisible to other connections until `commit()`. `with conn:` commits on success and rolls back on exception. Reads need no commit.

**Where:** `app.py:65` (commit), `scripts/seed_expenses.py:46-54` (all-or-nothing bulk insert).

```python
with conn:  # commits on success, rolls back on any error
    conn.executemany("INSERT INTO expenses (...) VALUES (?, ?, ?, ?, ?)", rows)
```

Note: `with conn` does not close the connection; you still call `conn.close()`.

**Practice:** If row 30 of 50 violates a constraint, how many rows are saved with `with conn:`? Without it and without commit?

## 14. `executemany`

**What:** Runs one parameterised statement for a list of tuples; shorter and faster than a Python loop of `execute`.

**Where:** `database/db.py:88-92`, `scripts/seed_expenses.py:48`, `tests/test_backend_connection.py:38-42`.

**Practice:** Insert three rows of your own into a temp DB with one `executemany` call.

## 15. Seeding and idempotence

**What:** Seeding inserts starter data. An idempotent seed is safe to run repeatedly: `seed_db()` returns early if any user exists, so restarting the app never duplicates the demo user (`demo@spendly.com`, password `demo123`, 8 expenses totalling ₹6,948). The scripts differ: `seed_user.py` adds a new random user each run (retrying until the email is unused), and `seed_expenses.py` appends rows each run.

**Where:** `database/db.py:59-94`, `scripts/seed_user.py:19-35`, `scripts/seed_expenses.py`.

```python
if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
    conn.close()
    return
```

**Practice:** Call `seed_db()` twice on a temp DB and confirm `COUNT(*)` of expenses stays 8.

## 16. Storing money as REAL (and its caveat)

**What:** `amount REAL NOT NULL` stores a binary floating-point number. Floats cannot represent most decimals exactly (`0.1 + 0.2 = 0.30000000000000004`), so sums can drift by tiny fractions. The project copes by rounding at the edge: `round(float(total), 2)` (`database/queries.py:82`), and shows amounts as `₹6,948.00`. Safer alternative: store integer paise (₹450.00 becomes `45000`), sum integers, divide by 100 only for display.

**Where:** `database/db.py:47`, `database/queries.py:54, 82, 109`.

```sql
amount REAL NOT NULL      -- today
amount_paise INTEGER NOT NULL  -- safer alternative, 45000 = ₹450.00
```

**Practice:** In Python, sum `[0.1] * 10` and compare to `1.0`. Then sum `[10] * 10` paise and divide by 100.

## 17. Storing dates: ISO text and `datetime('now')`

**What:** SQLite has no real date type. Dates are stored as `TEXT` in ISO `YYYY-MM-DD`, which sorts correctly as plain text (so `ORDER BY date` works). `DEFAULT (datetime('now'))` fills `created_at` with a UTC `YYYY-MM-DD HH:MM:SS` string when you omit it. Python parses them back with `strptime` and `date.isoformat()` produces them.

**Where:** `database/db.py:41, 49, 76` (`.isoformat()`), `database/queries.py:28` (`created_at[:10]` then `strptime`), `:51` (reformat to `20 Mar 2026`).

```python
datetime.strptime(row["date"], "%Y-%m-%d").strftime("%d %b %Y")
```

**Practice:** Why would storing `20/03/2026` break `ORDER BY date DESC`?

## 18. The gitignored `expense_tracker.db`

**What:** The database is a single binary file at the project root, created on first run by `init_db()`. It is listed in `.gitignore` (line 2) because it holds local data and password hashes; each developer builds their own from `init_db()` + `seed_db()`. `DB_PATH` is computed from `db.py`'s location (`database/db.py:7-10`).

**Practice:** Delete a copy of the file (never your only one if you care about the data) and restart the app. What gets recreated?

## 19. Testing against a temp DB with monkeypatch

**What:** Tests must not touch the real DB. The fixture points `DB_PATH` at a per-test temporary file with pytest's `tmp_path` and `monkeypatch`, then builds a fresh schema and seed. This works because `get_db()` reads the module global `DB_PATH` on every call, and `monkeypatch` restores it afterwards.

**Where:** `tests/test_backend_connection.py:15-21`; helpers `add_user` / `add_expenses` at `:24-44`.

```python
monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
db.init_db()
db.seed_db()
```

**Practice:** Add a test that inserts an expense for user id 9999 and expects `sqlite3.IntegrityError` (hint: needs the foreign-keys pragma).

---

## Not in the project yet

- **Indexes** (e.g. on `expenses(user_id, date)`) to speed up scoped queries as data grows.
- **Migrations** (altering an existing DB safely; today you edit `CREATE TABLE` and recreate the file).
- **ORMs** (SQLAlchemy and similar); the project uses raw SQL on purpose.
- **Joins** beyond a single table; no query reads `users` and `expenses` together.
- `UPDATE` / `DELETE` statements (edit/delete expense routes are still stubs), `ON DELETE CASCADE`, `CHECK` constraints (e.g. `amount > 0`), connection pooling.

## Inspecting the real DB from the sqlite3 CLI

Run from the project root. Opening read-only avoids accidental writes.

```bash
sqlite3 -readonly expense_tracker.db
```

Inside the shell:

```sql
.tables                          -- list tables
.schema expenses                 -- show CREATE statement
.headers on
.mode column
SELECT id, name, email, created_at FROM users;
SELECT COUNT(*), COALESCE(SUM(amount),0) FROM expenses WHERE user_id = 1;
SELECT category, SUM(amount) FROM expenses WHERE user_id = 1 GROUP BY category;
PRAGMA foreign_keys;             -- 0 here: the pragma is per connection
PRAGMA foreign_key_list(expenses);
.quit
```

One-liner without entering the shell:

```bash
sqlite3 -readonly -header -column expense_tracker.db "SELECT * FROM expenses ORDER BY date DESC LIMIT 5;"
```
