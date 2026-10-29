import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(7)

FIRST = ["Arun", "Meena", "Ravi", "Priya", "Karthik", "Divya", "Suresh", "Anita",
         "Vijay", "Lakshmi", "Rahul", "Sneha", "Manoj", "Kavya", "Ganesh", "Pooja",
         "Dinesh", "Nithya", "Ashok", "Revathi"]
LAST = ["Kumar", "Raj", "Nair", "Iyer", "Reddy", "Sharma", "Das", "Pillai", "Menon", "Singh"]
CITIES = ["Chennai", "Mumbai", "Delhi", "Bengaluru", "Hyderabad"]


def person():
    return f"{random.choice(FIRST)} {random.choice(LAST)}"


def random_date(start, days):
    return (start + timedelta(days=random.randint(0, days))).isoformat()


def new_db(filename):
    if os.path.exists(filename):
        os.remove(filename)
    return sqlite3.connect(filename)


# ---------- 1. sales.db ----------
conn = new_db("sales.db")
conn.executescript("""
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT, price REAL);
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER,
                     quantity INTEGER, order_date TEXT);
""")
products = [
    ("Laptop", "Computers", 55000), ("Tablet", "Computers", 25000),
    ("Monitor", "Computers", 12000), ("Headphones", "Audio", 2500),
    ("Speaker", "Audio", 3500), ("Earbuds", "Audio", 1800),
    ("Mouse", "Accessories", 500), ("Keyboard", "Accessories", 1500),
    ("Webcam", "Accessories", 2200), ("USB Hub", "Accessories", 900),
]
conn.executemany("INSERT INTO products (name, category, price) VALUES (?, ?, ?)", products)
conn.executemany("INSERT INTO customers (name, city) VALUES (?, ?)",
                 [(person(), random.choice(CITIES)) for _ in range(60)])
start = date(2026, 1, 1)
conn.executemany(
    "INSERT INTO orders (customer_id, product_id, quantity, order_date) VALUES (?, ?, ?, ?)",
    [(random.randint(1, 60), random.randint(1, len(products)),
      random.randint(1, 5), random_date(start, 300)) for _ in range(400)],
)
conn.commit()
conn.close()
print("sales.db created: products, customers, orders (400 orders)")

# ---------- 2. school.db ----------
conn = new_db("school.db")
conn.executescript("""
CREATE TABLE students (id INTEGER PRIMARY KEY, name TEXT, grade INTEGER, section TEXT, city TEXT);
CREATE TABLE marks (id INTEGER PRIMARY KEY, student_id INTEGER, subject TEXT, term TEXT, score INTEGER);
""")
conn.executemany(
    "INSERT INTO students (name, grade, section, city) VALUES (?, ?, ?, ?)",
    [(person(), random.choice([8, 9, 10]), random.choice(["A", "B"]), random.choice(CITIES))
     for _ in range(60)],
)
subjects = ["Maths", "Science", "English", "Social", "Tamil"]
marks = []
for student_id in range(1, 61):
    ability = random.randint(50, 85)
    for term in ["Term 1", "Term 2"]:
        for subject in subjects:
            score = max(20, min(100, int(random.gauss(ability, 12))))
            marks.append((student_id, subject, term, score))
conn.executemany("INSERT INTO marks (student_id, subject, term, score) VALUES (?, ?, ?, ?)", marks)
conn.commit()
conn.close()
print("school.db created: students, marks (600 marks)")

# ---------- 3. hospital.db ----------
conn = new_db("hospital.db")
conn.executescript("""
CREATE TABLE doctors (id INTEGER PRIMARY KEY, name TEXT, department TEXT);
CREATE TABLE patients (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, city TEXT);
CREATE TABLE visits (id INTEGER PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER,
                     visit_date TEXT, fee REAL);
""")
departments = ["Cardiology", "Orthopedics", "Pediatrics", "Dermatology", "General Medicine"]
conn.executemany("INSERT INTO doctors (name, department) VALUES (?, ?)",
                 [("Dr. " + person(), departments[i % 5]) for i in range(10)])
conn.executemany("INSERT INTO patients (name, age, city) VALUES (?, ?, ?)",
                 [(person(), random.randint(1, 85), random.choice(CITIES)) for _ in range(120)])
conn.executemany(
    "INSERT INTO visits (patient_id, doctor_id, visit_date, fee) VALUES (?, ?, ?, ?)",
    [(random.randint(1, 120), random.randint(1, 10), random_date(date(2026, 1, 1), 300),
      random.choice([300, 500, 800, 1200, 1500, 2500])) for _ in range(500)],
)
conn.commit()
conn.close()
print("hospital.db created: doctors, patients, visits (500 visits)")

# ---------- 4. hr.db ----------
conn = new_db("hr.db")
conn.executescript("""
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT, budget REAL);
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER,
                        role TEXT, salary REAL, hire_date TEXT, city TEXT);
""")
conn.executemany(
    "INSERT INTO departments (name, budget) VALUES (?, ?)",
    [("Engineering", 5000000), ("Sales", 3000000), ("HR", 1200000),
     ("Finance", 2000000), ("Support", 1500000)],
)
base = {"Junior": 30000, "Mid": 50000, "Senior": 80000, "Lead": 120000}
employees = []
for _ in range(80):
    role = random.choice(list(base.keys()))
    salary = round(random.gauss(base[role], base[role] * 0.12), -2)
    employees.append((person(), random.randint(1, 5), role, salary,
                      random_date(date(2018, 1, 1), 2800), random.choice(CITIES)))
conn.executemany(
    "INSERT INTO employees (name, department_id, role, salary, hire_date, city) VALUES (?, ?, ?, ?, ?, ?)",
    employees,
)
conn.commit()
conn.close()
print("hr.db created: departments, employees (80 employees)")