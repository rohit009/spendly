# Python Topics for Reading Spendly

This guide lists only the Python language features that actually appear in
this project. Flask is covered in `flask-backend-topics.md` and SQL in
`database-topics.md`, so neither is repeated here. Line numbers refer to the
files as they are today; they may drift slightly as code changes.

## Suggested learning order

1. Imports, modules and `__main__` (1-2)
2. Strings, f-strings, number formatting (3-4)
3. Lists, tuples, dicts, comprehensions (5-7)
4. Functions, default args, closures, decorators (8-10)
5. Truthiness, `or` fallbacks, `None` (11)
6. Exceptions and `try/finally` (12-13)
7. `datetime`, `os.path`, `os.environ` (14-15)
8. Scripts: `sys.argv`, `sys.exit`, `random` (16-17)
9. pytest basics (18-20)

---

## 1. Imports and module-level code
A module is a `.py` file; `import` runs it once and gives you its names. Code
at the top level (outside any `def`) runs at import time.
- `app.py:1-13` imports stdlib, third-party, then local modules; `app.py:15-21` creates `app` and seeds the DB at import time.
- `from x import (a, b)` with parentheses spans several lines (`app.py:8-13`).
- `import database.db as db` aliases a module (`tests/test_profile.py:6`).

Exercise: in a REPL run `import os; print(os.name)`, then `from datetime import date; print(date.today())`.

## 2. `if __name__ == "__main__"`
`__name__` is `"__main__"` only when the file is run directly, not imported.
- `app.py:182-183` starts the dev server only for `python app.py`; tests importing `app` do not start it.

Exercise: make `hello.py` that prints `ran` at top level and `main` under the guard; run it, then `import hello` from another file.

## 3. Strings and string methods
Strings are immutable; methods return new strings. `strip()` trims whitespace, `lower()` lowercases, `split(sep, maxsplit)` splits, slicing `s[:10]` / `s[-3:]` takes parts.
- `app.py:41-42`: `request.form.get("email", "").strip().lower()` (method chaining).
- `app.py:50`: `email.split("@", 1)[1]` takes the text after the first `@`.
- `queries.py:27`: `"".join(word[0] for word in name.split()[:2]).upper()` builds initials.
- `queries.py:28`: `row["created_at"][:10]` slices off the date part.

Exercise: turn `"  Asha Rao "` into `"AR"` using only strip, split, join, upper.

## 4. f-strings and number formatting
`f"...{expr:spec}..."` embeds expressions. Specs: `:.2f` two decimals, `:,` thousands commas, `:<14` left-pad to width 14.
- `app.py:133`: `f"{abs(value):.2f}"` gives e.g. `"1234.50"`.
- `scripts/seed_expenses.py:62`: `f"{r[2]:<14} ₹{r[1]:,.0f}"` aligns a column and prints `₹2,299`.
- `app.py:143` returns `f"{sign}₹{whole}.{decimals}"`.

Exercise: print `f"{1850000:,.2f}"`; it gives `1,850,000.00`, not the Indian `18,50,000.00`. Why does `inr` need its own loop?

## 5. Lists and tuples
A list is mutable (`append`, `insert`, slicing); a tuple is a fixed, immutable group, often a record or SQL parameters. A one-item tuple needs a trailing comma.
- `db.py:12-20` `CATEGORIES` list; `db.py:78-87` a list of tuples, one per expense.
- `app.py:58`: `(email,)` is a one-item tuple for the SQL parameter.
- `app.py:138`: `groups.insert(0, head[-2:])` prepends; `app.py:142` joins `groups + [tail]`.
- `tests/test_backend_connection.py:41`: `(user_id, *r)` unpacks a tuple into a new one.

Exercise: given `r = (450, "Food")`, build `(1, *r)` and unpack it as `uid, amt, cat = ...`.

## 6. Dicts
Key-to-value maps. Access with `d[key]` (error if missing) or `d.get(key, default)`.
- `queries.py:29-34` returns a dict; `queries.py:80` returns a dict with `"—"` as a placeholder.
- `scripts/seed_expenses.py:12-20` `SPEC` maps category to a tuple; `SPEC[cat][2]` indexes into it.
- `app.py:35`: `session.get("user_id")` behaves like `dict.get`.
- `queries.py:114`: `result[0]["pct"] += ...` mutates a dict inside a list.

Exercise: build `{"Food": 450, "Bills": 1850}`, add `"Health": 650`, and print the total with `sum(d.values())`.

## 7. Comprehensions and generator expressions
`[expr for x in items]` builds a list in one line; add `if` to filter. Without brackets, as an argument to `sum`/`join`/`sorted`, it is a lazy generator expression.
- `queries.py:49-57` list of dicts from rows; `queries.py:106-113` same idea.
- `queries.py:102`: `sum(r["total"] for r in rows)`.
- `scripts/seed_expenses.py:23`: `(int(a) for a in sys.argv[1:4])` feeds tuple unpacking.
- `scripts/seed_expenses.py:37`: `[SPEC[c][2] for c in cats]`.
- Generators with `yield` are not written in this project.

Exercise: from `amounts = [450, 120, 1850]` build the list of amounts over `₹400`, then their sum.

## 8. Functions, parameters, default arguments
`def name(a, b=default)`. Defaults apply when the argument is omitted; keyword calls (`limit=3`) are clearer. A docstring is the first string in the body.
- `queries.py:38` `get_recent_transactions(user_id, limit=10)`, called with `limit=3` at `tests/test_backend_connection.py:110`.
- `tests/test_backend_connection.py:24` `add_user(name="Asha Rao", email=...)`.
- `app.py:152-163`: keyword arguments passed to `render_template`.

Exercise: write `rupees(amount, symbol="₹")` returning `f"{symbol}{amount:,.2f}"` and call it with and without `symbol`.

## 9. Nested functions and closures
A function defined inside another can read the outer function's variables.
- `app.py:45-46` (and `85-86`): `fail(error)` uses the enclosing `name` and `email`, so each error path is one short line.
- `db.py:75-76`: `day(d)` uses the enclosing `today`.

Exercise: write `make_adder(n)` returning an inner function that adds `n`; make an `add_rent` that adds `15000`.

## 10. Decorators
`@deco` above a `def` means `f = deco(f)`. Decorators with arguments are called first, then applied.
- `app.py:28`: `@app.route("/")`; `app.py:129`: `@app.template_filter("inr")` registers the function but returns it unchanged, so tests can import `inr` directly (`tests/test_profile.py:7`).
- `tests/test_profile.py:12`: `@pytest.fixture`; `:64`: `@pytest.mark.parametrize(...)`.

Exercise: write a decorator `shout` that uppercases a function's returned string, and apply it to `def greet(): return "hi"`.

## 11. Truthiness, `None`, `or` fallbacks, comparisons
Empty strings, `0`, `None`, `[]`, `{}` are falsy. `a or b` returns `a` if truthy else `b`. Test for `None` with `is None`.
- `app.py:48`: `if not name:`; `app.py:101`: `user is None or not check_password_hash(...)` short-circuits.
- `queries.py:52`: `row["description"] or ""` turns `None` into `""`.
- `queries.py:103`: `if not rows or not grand_total:` handles empty lists and zero.
- `app.py:134`, `app.py:140`: `if len(whole) > 3`, `if head:`.
- `app.py:132`: conditional expression `"-" if value < 0 else ""`.

Exercise: predict `bool("")`, `bool("0")`, `bool(0.0)`, `None or "—"`; then check in a REPL.

## 12. Exceptions
`try/except` handles a named error; `raise` signals one.
- `app.py:66`: `except sqlite3.IntegrityError` catches a duplicate email.
- `scripts/seed_expenses.py:22-27`: `raise ValueError` is used on purpose to jump to the `except ValueError` that prints usage; `int("x")` also raises it.
- `scripts/seed_expenses.py:52`: `except Exception as e` catches anything and shows `e`.

Exercise: write `to_amount(text)` that returns `float(text)` or `0.0` on `ValueError`.

## 13. `try/finally` and `with`
`finally` always runs, even after `return` or an error, so it is used to close resources. `with` does the same set-up/tear-down automatically.
- `app.py:57-69`, `queries.py:16-22`: `conn.close()` in `finally`; note the `return fail(...)` inside `try` still closes the connection.
- `scripts/seed_expenses.py:47`: `with conn:` commits on success and rolls back on error.

Exercise: write a function that `return`s inside `try` and prints `"closed"` in `finally`; call it and confirm the order.

## 14. `datetime` parsing and formatting
`strptime(text, fmt)` parses text to a datetime; `strftime(fmt)` formats it; `date.today()`, `timedelta`, `.isoformat()`, `.replace(day=...)`.
- `queries.py:28`: `datetime.strptime("2026-03-20", "%Y-%m-%d")`; `queries.py:33`: `.strftime("%B %Y")` gives `March 2026`; `queries.py:51`: `"%d %b %Y"` gives `20 Mar 2026`.
- `db.py:73-76`: `today.replace(day=min(d, today.day)).isoformat()` caps dates at today.
- `scripts/seed_expenses.py:35,43`: `today - timedelta(days=months * 30)`; subtracting dates gives a `timedelta` with `.days`.

Exercise: parse `"2026-01-05"` and print it as `05 Jan 2026`; then print the date 30 days later.

## 15. `os`, `os.path`, `os.environ`
`os.path.abspath/dirname/join` build file paths; `__file__` is the current file; `os.environ.get(key, default)` reads environment variables safely.
- `db.py:7-10`: `dirname(dirname(abspath(__file__)))` goes two levels up to the project root.
- `app.py:17`: `os.environ.get("SECRET_KEY", "dev-only-insecure-key")`.
- `tests/test_profile.py:9`: `pathlib.Path(__file__).resolve().parent.parent`, then `ROOT / "templates"` and `.read_text()` (a modern alternative).

Exercise: print the folder that contains your script, and the value of `HOME` with a default of `"unknown"`.

## 16. `sys.argv`, `sys.exit`, `sys.path`
`sys.argv` is the list of command-line words (`argv[0]` is the script). `sys.exit("msg")` prints the message to stderr and exits with failure. `sys.path` is where imports are searched.
- `scripts/seed_expenses.py:23-27`: `sys.argv[1:4]` read as `user_id count months`; `sys.exit(USAGE)`.
- `scripts/seed_expenses.py:6`, `seed_user.py:6`: `sys.path.insert(0, project_root)` lets `from database.db import ...` work when run from `scripts/`.

Exercise: write a script that takes an amount from `sys.argv[1]` and prints `₹` plus the amount doubled, with a usage message if missing.

## 17. `random`, loops and `print`
`random.choice(list)`, `choices(items, weights)`, `randint(a, b)` (inclusive), `sample(list, k)`. `for _ in range(n)` repeats n times; `while True` + `break` loops until a condition holds. `_` is a throwaway name.
- `seed_expenses.py:40-44` builds rows in a loop; `:41` weighted pick; `:57` `sorted(...)`; `:61` `random.sample(rows, min(5, len(rows)))`.
- `seed_user.py:21-25` retries random emails until an unused one is found.
- `app.py:137-141` a `while len(head) > 2:` loop does the Indian grouping.

Exercise: generate 5 random amounts between `₹50` and `₹800` and print each with `₹` and commas.

## 18. pytest basics: tests and `assert`
A test is a function named `test_*` in `tests/`; `assert expr` fails the test if false. Compare lists/dicts directly with `==`. Helper functions without the `test_` prefix are not run.
- `tests/test_profile.py:75-76`: `assert inr(value) == expected`.
- `tests/test_backend_connection.py:100,124`: `assert [r["description"] for r in rows] == [...]`, `sum(...) == 100`.
- Run: `venv/bin/pytest tests/test_profile.py::test_profile_requires_login`.

Exercise: write `test_inr_zero` asserting `inr(0) == "₹0.00"` and run it.

## 19. Fixtures, `tmp_path`, `monkeypatch`
A fixture is set-up code a test receives by naming it as a parameter. `tmp_path` is a fresh temporary folder per test; `monkeypatch.setattr(obj, "name", value)` swaps something for the duration of the test, then undoes it.
- `tests/test_backend_connection.py:15-21`: `client` fixture points `db.DB_PATH` at `tmp_path / "test.db"`, so tests never touch the real database. This works because `get_db()` reads `DB_PATH` at call time.
- Operator `/` on paths joins them: `tmp_path / "test.db"`.

Exercise: write a fixture `amounts` returning `[450, 120]` and a test asserting `sum(amounts) == 570`.

## 20. `parametrize` and test data
`@pytest.mark.parametrize("a, b", [(x1, y1), (x2, y2)])` runs one test per tuple.
- `tests/test_profile.py:64-76` tries `inr` with `0`, `999`, `1000`, `123456`, `-2500` (note `1234567.5` expects `₹12,34,567.50`).
- `tests/test_login_logout.py:83` parametrizes a single value, `path`.

Exercise: parametrize a test over `(450, "₹450.00")` and `(1850, "₹1,850.00")` for `inr`.

---

## Reading checklist
When you can explain these without notes, you can read the project's Python:
- why `fail()` can see `name` and `email` (topic 9);
- what `inr(123456)` does line by line (topics 3, 4, 5, 17);
- why `conn.close()` is in `finally` (topic 13);
- how a test uses `tmp_path` and `monkeypatch` to avoid touching the real DB (topic 19).
