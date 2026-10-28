import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    """Return a SQLite connection with dict-like rows and foreign keys on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables. Safe to call multiple times."""
    conn = get_db()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    """Insert a demo user and sample expenses, only if the DB is empty."""
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
        conn.close()
        return

    # pbkdf2 rather than Werkzeug's default scrypt, which needs OpenSSL
    # support that macOS's system Python (LibreSSL) lacks.
    password_hash = generate_password_hash("demo123", method="pbkdf2:sha256")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    # Days of the current month, capped at today so no date is in the future.
    today = date.today()

    def day(d):
        return today.replace(day=min(d, today.day)).isoformat()

    expenses = [
        (user_id, 450.00, "Food", day(1), "Groceries"),
        (user_id, 120.00, "Transport", day(3), "Auto rickshaw"),
        (user_id, 1850.00, "Bills", day(5), "Electricity bill"),
        (user_id, 650.00, "Health", day(8), "Pharmacy"),
        (user_id, 499.00, "Entertainment", day(12), "Movie tickets"),
        (user_id, 2299.00, "Shopping", day(15), "Shoes"),
        (user_id, 300.00, "Other", day(20), "Gift"),
        (user_id, 780.00, "Food", day(25), "Dinner out"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        expenses,
    )
    conn.commit()
    conn.close()
