import sqlite3
from google import genai
from google.genai import types


def run_query(sql: str) -> str:
    """Run a read-only SQL SELECT on the shop database (SQLite).
    Table: products(id, name, price, stock)."""
    if not sql.strip().lower().startswith("select"):
        return "Error: only SELECT queries are allowed."
    conn = sqlite3.connect("file:shop.db?mode=ro", uri=True)
    try:
        rows = conn.execute(sql).fetchall()
        return str(rows[:50])
    except Exception as e:
        return f"Error: {e}"
    finally:
        conn.close()


client = genai.Client()  # reads your key from GEMINI_API_KEY

chat = client.chats.create(
    model="gemini-3.5-flash",
    config=types.GenerateContentConfig(tools=[run_query]),
)

print("Shop bot ready! Type 'exit' to stop.")
while True:
    q = input("You: ")
    if q.lower() == "exit":
        break
    reply = chat.send_message(q)
    print("Bot:", reply.text)