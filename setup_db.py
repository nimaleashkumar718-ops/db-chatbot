import sqlite3

conn = sqlite3.connect("shop.db")
conn.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)")
conn.executemany(
    "INSERT INTO products (name, price, stock) VALUES (?, ?, ?)",
    [("Laptop", 55000, 10), ("Mouse", 500, 120), ("Keyboard", 1500, 45)],
)
conn.commit()
conn.close()
print("Database created!")