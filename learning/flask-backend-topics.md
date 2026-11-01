# Flask Backend Topics for Spendly

Spendly's backend is **Flask 3.1 + SQLite** (not FastAPI). This guide lists what to learn to understand it, in a suggested order. Line references are to `app.py` unless noted. The FastAPI equivalent is given for each topic in case you move to FastAPI later.

## Suggested learning order

1. Flask app, routes and methods
2. `request.form`, Jinja2 templates and filters, `url_for` and redirect
3. Sessions and `secret_key`
4. `sqlite3` basics with parameterised SQL, plus init and seed
5. Password hashing and the login and register flow
6. pytest client and monkeypatch fixtures
7. Only then the FastAPI mapping

---

## 1. Core Flask

| # | Topic | Where | FastAPI equivalent |
|---|---|---|---|
| 1 | App object and routing | 9; `@app.route` at 22, 27, 68, 117, 178 | `FastAPI()` with `@app.get` / `@app.post` |
| 2 | HTTP methods per route | `methods=["GET","POST"]` at 27 and 68 | Separate GET and POST functions |
| 3 | Form handling | `request.form.get(...)` at 35-37, 76-77 | `Form(...)` (needs python-multipart) or a Pydantic model |
| 4 | Jinja2 templates | `render_template`; `base.html` blocks and `extends` | `Jinja2Templates` + `TemplateResponse` (same Jinja syntax) |
| 5 | Custom template filter | `@app.template_filter("inr")` at 123, used as `\|inr` in `profile.html` | `templates.env.filters["inr"] = inr` |
| 6 | redirect and `url_for` | 30, 65, 100, 120, 181 | `RedirectResponse`, `request.url_for`, `StaticFiles` at `/static` |

## 2. Auth and security

| # | Topic | Where | FastAPI equivalent |
|---|---|---|---|
| 7 | Sessions with a signed cookie | 11, 29, 98-99, 119, 180 | Starlette `SessionMiddleware`, or JWT |
| 8 | Password hashing (werkzeug) | 57, 95, `database/db.py:68` | passlib/bcrypt or argon2 |
| 9 | Login guard, written inline | 180; reverse guard at 29 and 70 | `Depends(get_current_user)` |
| 10 | Hand-written validation | 42-47, 82-85, with a `fail()` helper that keeps entered values except the password | Pydantic models, `EmailStr` |
| 11 | Error handling | `IntegrityError` at 60 for duplicate emails; no 404/500 handlers | `HTTPException`, `@app.exception_handler` |

## 3. Database (`database/db.py`)

| # | Topic | FastAPI equivalent |
|---|---|---|
| 12 | `sqlite3`: `get_db()` with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`; `init_db` (`CREATE TABLE IF NOT EXISTS`); `seed_db`; parameterised `?` queries; manual `try/finally conn.close()` | Same module, or SQLAlchemy/SQLModel; `Depends(get_db)` generator that yields the connection |
| 13 | Startup init at lines 13-15 (`with app.app_context()`) | `lifespan` handler |

## 4. Other

- **Path converters:** `/expenses/<int:id>/edit` becomes `/expenses/{id}/edit` with `id: int`. These routes are still stubs.
- **Dev server:** `app.run(debug=True, port=5001)` becomes `uvicorn app:app --reload`.
- **Environment config:** `os.environ.get("SECRET_KEY", ...)` becomes pydantic-settings.
- **Testing:** the `client` fixture uses `tmp_path` and `monkeypatch.setattr(db, "DB_PATH", ...)`, and `client.session_transaction()` reads the session. In FastAPI this becomes `TestClient` and `app.dependency_overrides`. pytest-flask is installed but the tests use the plain `test_client`.
- **Scripts:** `scripts/seed_user.py` and `scripts/seed_expenses.py` are plain Python with nothing framework-specific.
- **Profile logic:** `_profile_summary` is pure Python aggregation. Step 5 will replace the hardcoded data with SQL queries.

## 5. Not in the project yet

You don't need these to follow the current backend:

- JSON/REST APIs
- Pydantic validation
- dependency injection
- async/await
- OAuth/JWT
- CSRF protection
- blueprints or an app factory
- an ORM or migrations
- CORS
- flash messages
- a login-required decorator
- rate limiting
- logging config
- auto-generated API docs
- expense CRUD (only stubs)
