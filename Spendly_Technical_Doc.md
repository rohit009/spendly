# Spendly - Technical Documentation

Audience: Senior iOS Engineer (8+ years of iOS development) who is new to backend and web frontend development. Focus: backend architecture and database design.

---

## Table of Contents

1. Project Overview
2. Tech Stack
3. Architecture Overview
4. Backend Deep Dive - Flask
5. Database Deep Dive - SQLite
6. Request Lifecycle (How Backend Handles Traffic)
7. iOS to Web / Backend Conceptual Mapping
8. References - Read More

---

## 1. Project Overview

Spendly is a personal expense tracker web application (Flask + SQLite) with the tagline "Track every rupee. Own your finances."

- Currency: INR, shown with Indian digit grouping (e.g. ₹1,23,456.00).
- Current stage: Steps 1-9 are complete. Users can register, log in and out, see a dashboard (summary stats, transaction history, category breakdown) with an optional date-range filter, and add, edit and delete their expenses. Analytics is a "coming soon" page.
- Tests: 291 pytest tests across `tests/`.
- Deployment: gunicorn on Railway (`Procfile`).

---

## 2. Tech Stack

- Language: Python 3.13
- Backend framework: Flask (3.1.3)
- Database: SQLite via Python sqlite3 module (no ORM)
- Password hashing: Werkzeug Security (3.1.6)
- Server-side rendering: Jinja2 (bundled with Flask)
- Static assets: Flask static folder (css/js)
- Testing: pytest, pytest-flask
- Production server: gunicorn (23.0.0) on Railway

---

## 3. Architecture Overview

The app is deliberately minimal (single module, no app factory, no blueprints).

Project layout:

- app.py: the entire Flask app - app instance, configuration, routes, input validation and Jinja filters.
- database/db.py: SQLite helpers - get_db, init_db, seed_db, and the CATEGORIES list.
- database/queries.py: every other SQL query (dashboard stats and expense create/read/update/delete), always scoped to one user_id.
- templates/: Jinja2 pages; all extend base.html.
- static/css/: style.css for shared styles plus one stylesheet per page.
- scripts/: seed scripts for extra demo users and expenses.
- tests/: pytest suite; each test runs against a temporary database file.

Bootstrap in app.py:

```python
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5001)
```

On startup the app context runs init_db (creates tables if missing) and seed_db (seeds demo data if the DB is empty). In production, gunicorn imports `app:app` instead of running the `__main__` block.

---

## 4. Backend Deep Dive - Flask

### 4.1 App Instance and Configuration

- Single module-level instance: app = Flask(__name__). No application factory pattern.
- `SECRET_KEY` signs the session cookie. Set it in production; without it a random key is generated on every start, so users are logged out after a restart.
- `SESSION_COOKIE_SAMESITE = "Lax"` stops browsers sending the session cookie on cross-site POSTs (basic CSRF protection).
- Locally: debug mode on port 5001 (set `FLASK_DEBUG=0` to turn debug off).

### 4.2 Routes

| Route | Methods | Login required | What it does |
|---|---|---|---|
| `/` | GET | No | Landing page |
| `/register` | GET, POST | No | Sign-up form; creates a user, then redirects to login |
| `/login` | GET, POST | No | Checks credentials, stores `user_id` in the session |
| `/logout` | GET | No | Clears the session, redirects to the landing page |
| `/terms`, `/privacy` | GET | No | Legal pages |
| `/profile` | GET | Yes | Dashboard; optional `?from=YYYY-MM-DD&to=YYYY-MM-DD` filter |
| `/analytics` | GET | Yes | Coming-soon page |
| `/expenses/add` | GET, POST | Yes | Add-expense form |
| `/expenses/<int:id>/edit` | GET, POST | Yes | Same form, pre-filled |
| `/expenses/<int:id>/delete` | GET, POST | Yes | GET shows a confirmation page; POST deletes |

Logged-in routes check `session.get("user_id")` and redirect to `/login` if it is missing. If the session points at a user that no longer exists, the session is cleared.

### 4.3 Request to Response Flow

1. Client (browser today, future iOS app) sends an HTTP request.
2. Flask WSGI stack matches the URL rule and method against registered routes.
3. The matched view function executes: it reads `request.form` / `request.args` and the session, and calls query helpers.
4. The view returns either `render_template("x.html", ...)`, which renders a Jinja2 template into HTML, or `redirect(url_for(...))` after a successful POST (the Post/Redirect/Get pattern, so refreshing the page never re-submits a form).

### 4.4 Authentication and Password Hashing (Werkzeug)

- Passwords are stored via `werkzeug.security.generate_password_hash` (Werkzeug 3.x defaults to scrypt with a random salt) and verified with `check_password_hash`.
- Registration rules: name required, valid-looking email (stored lower-case, unique), password at least 8 characters.
- Login returns one generic error, "Invalid email or password.", so it never reveals whether an email is registered.
- On successful login the session is cleared and then `session["user_id"]` is set.

### 4.5 Input Validation

Validation happens on the server in small helper functions in app.py:

- `_parse_amount`: parses with `Decimal`, allows at most 2 decimals, and limits the amount to more than ₹0 and at most ₹1,00,00,000.
- `_parse_date` / `_parse_range`: only accept zero-padded `YYYY-MM-DD` dates (so text comparison in SQL stays correct) and require From on or before To.
- `_validate_expense`: shared by add and edit; checks the amount, a category from `CATEGORIES`, a valid date that is not in the future, and a description of up to 200 characters.

On an error the form is re-rendered with the user's input echoed back and a message, rather than a redirect.

### 4.6 Authorization: Expenses Belong to Their Owner

Every expense query includes `WHERE ... AND user_id = ?`. Edit and delete look the expense up with `get_expense(user_id, id)`, and return 404 when it is missing or owned by someone else. The two cases look identical, so other users' expense ids can't be discovered by probing.

### 4.7 Jinja Filters

- `inr`: formats a number as rupees with Indian digit grouping, e.g. `1234567` becomes `₹12,34,567.00`.
- `date_label`: formats an ISO date as e.g. `01 Nov 2026`.

### 4.8 Known Gaps

- No CSRF tokens on forms; protection relies on `SameSite=Lax` cookies.
- No JSON API yet; every route returns HTML.
- Analytics is a placeholder page.

---

## 5. Database Deep Dive - SQLite

### 5.1 Connection Helper

```python
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

- A new connection is opened per operation and closed after use, in a `try/finally` (no pooling).
- sqlite3.Row allows dictionary-style access, e.g. row["email"].
- PRAGMA foreign_keys = ON enables foreign key enforcement (off by default in SQLite).
- `DB_PATH` points at `expense_tracker.db` in the project root (gitignored). Tests point it at a temporary file instead.

### 5.2 Schema

users table:

```sql
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TEXT DEFAULT (datetime('now'))
);
```

expenses table:

```sql
CREATE TABLE IF NOT EXISTS expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      REAL NOT NULL,
    category    TEXT NOT NULL,
    date        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

### 5.3 Key Design Points

- Relationship: users (1) to expenses (N) via expenses.user_id -> users.id foreign key. In iOS terms: think of it as a to-many relationship (user has many transactions).
- amount is stored as REAL (float). Input is validated as a `Decimal` with at most 2 decimals before it is stored, but for a real financial app, storing integer paise (minor units) is safer against float precision issues.
- date is stored as ISO text YYYY-MM-DD, so string comparison sorts and filters dates correctly.
- category is a plain TEXT column, checked against the Python-side `CATEGORIES` list (Food, Transport, Bills, Health, Entertainment, Shopping, Other).
- A blank description is stored as NULL.

### 5.4 Query Layer (database/queries.py)

All SQL is parameterised (`?` placeholders, never string formatting of user input) and scoped to one user_id.

- `get_user_by_id`: name, email, initials and "member since" month for the profile header.
- `get_summary_stats`: total spent, transaction count and top category (`SUM`, `COUNT`, `GROUP BY ... ORDER BY SUM(amount) DESC`).
- `get_recent_transactions`: newest expenses first, limited to 10.
- `get_category_breakdown`: total per category with percentages that always add up to 100.
- The three dashboard queries share `_date_clause`, which adds `AND date >= ?` / `AND date <= ?` only when a filter is set.
- `create_expense`, `get_expense`, `update_expense`, `delete_expense_row`: write helpers. Update and delete return whether exactly one row changed, so the route can return 404 otherwise.

### 5.5 Seeding Logic

seed_db: skips if any user already exists, inserts a demo user (demo@spendly.com / demo123, hashed via Werkzeug), and inserts 8 sample expenses with dates in the current month (capped at today, so none are in the future). `scripts/seed_user.py` and `scripts/seed_expenses.py` add more demo data on demand.

---

## 6. Request Lifecycle - How the Backend Handles Traffic

Example: adding an expense.

1. Browser -> `GET /expenses/add` -> route checks the session -> renders the empty form (date defaults to today).
2. User submits -> `POST /expenses/add` with form fields `amount`, `category`, `date`, `description`.
3. Flask parses the form into `request.form`; `_validate_expense` checks every field.
4. Invalid: the same form is rendered again with the error and the user's input (HTTP 200).
5. Valid: `create_expense` inserts the row, then the route redirects to `/profile` (HTTP 302).
6. Browser follows the redirect -> `GET /profile` -> the dashboard queries run -> Jinja2 renders the updated page.

In production the request first goes through gunicorn (the WSGI server) on Railway instead of Flask's development server.

---

## 7. iOS to Web / Backend Conceptual Mapping

| iOS Concept | Web Backend Equivalent |
|---|---|
| URL path + HTTP method + handler | Flask route + view function |
| URLSession data task | HTTP client to Flask server |
| JSON body (e.g., POST /api/expenses) | Flask route returning jsonify (not built yet) |
| View Controller / response handling | Flask view returning response |
| Storyboard / SwiftUI view | Jinja2 template rendered on the server |
| Form validation in the view model | Validation helpers in app.py (always on the server) |
| Core Data / Realm model | SQL tables + relationships (SQLite here) |
| NSFetchRequest with predicate | Parameterised SQL with `WHERE user_id = ?` |
| Keychain-stored token | Signed session cookie |
| XCTest | pytest + Flask test client |

When the backend evolves to serve an iOS client, expect a shift from server-rendered HTML (render_template) to JSON responses (jsonify), and from session cookies to tokens. The route structure and the query layer can stay largely the same.

---

## 8. References - Read More

### Flask (Backend Framework)
- Official docs: https://flask.palletsprojects.com/
- Flask Mega-Tutorial (Parts I-X) by Miguel Grinberg: https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world

### Werkzeug (Security / Utilities)
- Security documentation (password hashing): https://werkzeug.palletsprojects.com/en/stable/security/

### SQLite (Database)
- Official SQLite documentation: https://www.sqlite.org/docs.html
- Foreign keys PRAGMA: https://www.sqlite.org/pragma.html#pragma_foreign_keys
- Python sqlite3 module docs: https://docs.python.org/3/library/sqlite3.html

### Jinja2 (Templating)
- Official docs: https://jinja.palletsprojects.com/

### Testing
- pytest-flask: https://pytest-flask.readthedocs.io/

### Deployment
- gunicorn: https://gunicorn.org/
- Railway docs: https://docs.railway.com/

---

End of document.
