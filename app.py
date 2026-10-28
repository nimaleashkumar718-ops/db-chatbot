import sqlite3
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
MAX_ROWS = 50

st.set_page_config(page_title="Database Chatbot", page_icon="💬")
st.title("💬 Chat with your database")


# ---------- The connector: reads the structure of the database ----------
def get_schema(db_file):
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    lines = []
    for (table,) in tables:
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        col_text = ", ".join(f"{c[1]} {c[2]}" for c in cols)
        lines.append(f"{table}({col_text})")
    conn.close()
    return "\n".join(lines)


# ---------- Creates the AI chat connected to that database ----------
@st.cache_resource
def get_client():
    return genai.Client()

def make_chat(db_file, schema):
    def run_query(sql: str) -> str:
        """Run a read-only SQL SELECT query on the connected database."""
        if not sql.strip().lower().startswith("select"):
            return "Error: only SELECT queries are allowed."
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        try:
            rows = conn.execute(sql).fetchall()
            return str(rows[:MAX_ROWS])
        except Exception as e:
            return f"Error: {e}"
        finally:
            conn.close()

    client = get_client()
    return client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            tools=[run_query],
            system_instruction=(
                "You answer questions using the connected SQLite database. "
                "Use the run_query tool to get data, and answer only from its results. "
                f"Database structure:\n{schema}"
            ),
        ),
    )


# ---------- Left panel: the Connect form ----------
with st.sidebar:
    st.header("Connect")
    db_type = st.selectbox("Database type", ["SQLite"])
    db_file = st.text_input("Database file name", value="shop.db")

    if st.button("Connect"):
        try:
            schema = get_schema(db_file)
            st.session_state.chat = make_chat(db_file, schema)
            st.session_state.schema = schema
            st.session_state.db_file = db_file
            st.session_state.messages = []
            st.success("Connected!")
        except Exception as e:
            st.error(f"Could not connect: {e}")


# ---------- Main area: the chat window ----------
if "chat" not in st.session_state:
    st.info("Choose a database in the left panel and click Connect.")
    st.stop()

st.caption(f"Connected to: {st.session_state.db_file}")
with st.expander("Tables found"):
    st.code(st.session_state.schema)

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

question = st.chat_input("Ask a question about your data")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = st.session_state.chat.send_message(question).text
            except Exception as e:
                answer = f"Error: {e}"
        st.write(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})