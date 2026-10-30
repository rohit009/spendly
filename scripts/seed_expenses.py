import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import get_db

USAGE = "Usage: /seed-expenses <user_id> <count> <months>\nExample: /seed-expenses 1 50 6"

# category: (min ₹, max ₹, weight, descriptions)
SPEC = {
    "Food": (50, 800, 35, ["Groceries", "Swiggy order", "Chai and samosa", "Veg thali", "Dinner out", "Vegetables", "Zomato order"]),
    "Transport": (20, 500, 20, ["Auto rickshaw", "Metro recharge", "Ola cab", "Petrol", "Bus pass", "Uber ride"]),
    "Bills": (200, 3000, 15, ["Electricity bill", "Mobile recharge", "Broadband bill", "Water bill", "Gas cylinder"]),
    "Shopping": (200, 5000, 12, ["Shoes", "Kurta", "Amazon order", "Headphones", "Home decor", "Flipkart order"]),
    "Other": (50, 1000, 8, ["Gift", "Donation", "Stationery", "Haircut", "Laundry"]),
    "Health": (100, 2000, 6, ["Pharmacy", "Doctor consultation", "Lab tests", "Vitamins", "Dental checkup"]),
    "Entertainment": (100, 1500, 4, ["Movie tickets", "Netflix subscription", "Concert pass", "Gaming", "Bowling"]),
}

try:
    user_id, count, months = (int(a) for a in sys.argv[1:4])
    if len(sys.argv) != 4 or count < 1 or months < 1:
        raise ValueError
except ValueError:
    sys.exit(USAGE)

conn = get_db()
if not conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
    conn.close()
    sys.exit(f"No user found with id {user_id}.")

today = date.today()
start = today - timedelta(days=months * 30)
cats = list(SPEC)
weights = [SPEC[c][2] for c in cats]

rows = []
for _ in range(count):
    cat = random.choices(cats, weights)[0]
    lo, hi, _, descs = SPEC[cat]
    d = start + timedelta(days=random.randint(0, (today - start).days))
    rows.append((user_id, float(random.randint(lo, hi)), cat, d.isoformat(), random.choice(descs)))

try:
    with conn:  # single transaction: commits on success, rolls back on any error
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
except Exception as e:
    conn.close()
    sys.exit(f"Insert failed, nothing was saved: {e}")
conn.close()

dates = sorted(r[3] for r in rows)
print(f"Inserted {len(rows)} expenses for user {user_id}")
print(f"Date range: {dates[0]} to {dates[-1]}\n")
print("Sample records:")
for r in random.sample(rows, min(5, len(rows))):
    print(f"  {r[3]}  {r[2]:<14} ₹{r[1]:,.0f}  {r[4]}")
