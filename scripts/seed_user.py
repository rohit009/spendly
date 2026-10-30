import os
import random
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from werkzeug.security import generate_password_hash
from database.db import get_db, init_db

FIRST = ["Aarav", "Rahul", "Priya", "Ananya", "Vikram", "Sneha", "Arjun", "Kavya",
         "Rohan", "Ishita", "Siddharth", "Meera", "Karthik", "Lakshmi", "Aditya",
         "Pooja", "Harpreet", "Gurpreet", "Sourav", "Ritika", "Nikhil", "Divya",
         "Venkatesh", "Swati", "Amit", "Neha", "Manoj", "Deepika", "Rajesh", "Anjali"]
LAST = ["Sharma", "Verma", "Patel", "Iyer", "Reddy", "Nair", "Gupta", "Singh",
        "Banerjee", "Chatterjee", "Mukherjee", "Deshmukh", "Kulkarni", "Joshi",
        "Menon", "Pillai", "Rao", "Agarwal", "Mehta", "Shah", "Das", "Bose",
        "Gill", "Sandhu", "Naidu", "Patil", "Kapoor", "Malhotra", "Mishra", "Yadav"]

init_db()
conn = get_db()
while True:
    first, last = random.choice(FIRST), random.choice(LAST)
    email = f"{first.lower()}.{last.lower()}{random.randint(10, 999)}@gmail.com"
    if not conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        break

cursor = conn.execute(
    "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
    (f"{first} {last}", email, generate_password_hash("password123"),
     datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
)
conn.commit()
row = conn.execute("SELECT id, name, email FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
conn.close()
print(f"id:    {row['id']}\nname:  {row['name']}\nemail: {row['email']}")
