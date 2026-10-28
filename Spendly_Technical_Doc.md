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

- Currency: INR
- Current stage: early teaching-project stage - the database layer (Step 1) is implemented; auth and expense features are stubbed for upcoming steps.

---

## 2. Tech Stack

- Language: Python
- Backend framework: Flask (3.1.3)
- Database: SQLite via Python sqlite3 module
- Password hashing: Werkzeug Security (3.1.6)
- Server-side rendering: Jinja2 (bundled with Flask)
- Static assets: Flask static folder (css/js)
- Testing: pytest, pytest-flask

---

## 3. Architecture Overview

The app is deliberately minimal (single module, no app factory yet).

Project layout:

- app.py: the entire Flask app - app instance, routes, bootstrap.
- database/db.py: SQLite helpers - get_db, init_db, seed_db.

Bootstrap in app.py:

```python
app = Flask(__name__)

with app.app_context():
    init_db()
    seed_db()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
```

On startup the app context runs init_db (creates tables if missing) and seed_db (seeds demo data if DB is empty).

---

## 4. Backend Deep Dive - Flask

### 4.1 App Instance

- Single module-level instance: app = Flask(__name__). No application factory pattern yet.
- Debug mode enabled; listens on port 5001.

### 4.2 Routing

Routes are registered with @app.route decorators. Path variables use angle-bracket syntax, e.g. @app.route("/expenses/<int:id>/edit").

### 4.3 Request to Response Flow

1. Client (browser today, future iOS app) sends an HTTP request.
2. Flask WSGI stack matches the URL rule and method against registered routes.
3. The matched view function executes.
4. The view returns either a plain string (Flask converts it to an HTML response) or render_template("x.html", ...) which renders a Jinja2 template into an HTML response.

### 4.4 Password Hashing (Werkzeug)

- Passwords stored via werkzeug.security.generate_password_hash.
- Werkzeug defaults to PBKDF2 hashing with salt - secure one-way hashing for storing credentials.
- Verification would use check_password_hash.

### 4.5 Known Gaps

- Auth forms in templates already use method="POST", but the /login and /register routes currently accept GET only - a known gap to be filled in upcoming steps.

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

- A new connection is opened per operation and closed after use (no pooling in this teaching implementation).
- sqlite3.Row allows dictionary-style access, e.g. row["email"].
- PRAGMA foreign_keys = ON enables foreign key enforcement (off by default in SQLite).

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
- amount is stored as REAL (float) - note: for financial apps, storing integer minor units or using Decimal is often preferred to avoid float precision issues.
- date stored as ISO text YYYY-MM-DD.
- category is a plain TEXT column with a Python-side constant list (CATEGORIES).

### 5.4 Seeding Logic

seed_db: skips if any user already exists, inserts demo user (demo@spendly.com / demo123, hashed via Werkzeug), and inserts 8 sample expenses with dates relative to the current month (capped at today).

---

## 6. Request Lifecycle - How the Backend Handles Traffic

Current simplified flow for a page like /login:

Browser (or future iOS client) -> HTTP GET /login -> Flask dev server (WSGI) -> route matches -> view: login() -> render_template -> Jinja2 renders -> HTML response (200 OK) -> Browser renders form.

Future flow will extend this with:
- Form POST handling (request.form / request.get_json)
- Session/cookie management (Flask session)
- JSON API responses for potential native clients.

---

## 7. iOS to Web / Backend Conceptual Mapping

| iOS Concept | Web Backend Equivalent |
|---|---|
| URL path + HTTP method + handler | Flask route + view function |
| URLSession data task | HTTP client to Flask server |
| JSON body (e.g., POST /api/expenses) | Flask route returning jsonify |
| View Controller / response handling | Flask view returning response |
| Core Data / Realm model | SQL tables + relationships (SQLite here) |
| Keychain-stored token | Session cookie / token (future) |

When the backend evolves to serve an iOS client, expect a shift from server-rendered HTML (render_template) to JSON responses (jsonify) - the route structure and DB layer will largely remain reusable.

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

---

End of document.
