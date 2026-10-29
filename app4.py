import os
import re
import sqlite3
import textwrap

import numpy as np
import pandas as pd
import streamlit as st
from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash"
MAX_ROWS = 200

EXAMPLES = [
    "Show all the data in the first table",
    "How many rows does each table have?",
    "Compare the numbers in the biggest table as a chart",
    "Show statistics of the main number column",
]

st.set_page_config(page_title="Database Chatbot", page_icon="📊", layout="wide")

# ---------- Styling: the "clothes" of the page (CSS) ----------
st.markdown(
    """
<style>
.hero {
    background: linear-gradient(90deg, #6366f1, #8b5cf6, #ec4899);
    padding: 1.4rem 1.8rem;
    border-radius: 16px;
    margin-bottom: 1.2rem;
}
.hero h1 { margin: 0; font-size: 2rem; color: white !important; }
.hero p { margin: 0.3rem 0 0 0; color: white; opacity: 0.92; }
[data-testid="stChatMessage"] { border-radius: 14px; padding: 0.6rem 1rem; }
div[data-testid="stMetric"] {
    background: rgba(99, 102, 241, 0.12);
    border: 1px solid rgba(99, 102, 241, 0.35);
    padding: 0.8rem 1rem;
    border-radius: 12px;
}
.stButton > button { border-radius: 10px; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <h1>📊 Chat with your database</h1>
  <p>Ask in plain English. Get answers, grids, charts, statistics, and visual explanations.</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------- The flow chart of the whole app (written in a diagram language called DOT) ----------
APP_FLOW = """
digraph {
  rankdir=TB;
  bgcolor="transparent";
  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#6366f1", fillcolor="#eef2ff", fontcolor="#1e1b4b"];
  edge [color="#8b5cf6"];
  user [label="1. You type a question\\nin the browser"];
  app [label="2. The app (Python + Streamlit)\\nsends it to the AI"];
  ai [label="3. AI (Gemini, through the API)\\nunderstands it and writes SQL"];
  tool [label="4. run_query tool\\n(only SELECT is allowed)"];
  db [label="5. Database file\\n(for example shop.db)", shape=cylinder];
  notes [label="6. Notepad saves\\nthe rows it got"];
  show [label="7. You see the sentence,\\ngrid, chart, stats and explanation", fillcolor="#fce7f3", color="#ec4899"];
  user -> app -> ai;
  ai -> tool [dir=both];
  tool -> db [dir=both];
  tool -> notes;
  notes -> show;
  app -> show;
}
"""


# ---------- Small helpers ----------
def clean_text(text, limit=60):
    text = " ".join(str(text).split())
    text = text.replace('"', "'").replace("\\", " ")
    if len(text) > limit:
        text = text[:limit] + "..."
    return "\\n".join(textwrap.wrap(text, 28)) or "-"


def short(text, limit=22):
    text = str(text).replace('"', "'").replace("\\", " ")
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def format_number(value):
    value = float(value)
    if value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def numeric_columns(df):
    cols = []
    for c in df.columns:
        name = str(c).lower().replace("_", " ").strip()
        is_id = name == "id" or name.endswith(" id")
        if pd.api.types.is_numeric_dtype(df[c]) and not is_id:
            cols.append(c)
    return cols


# ---------- Reads the SQL and lists the steps in plain English ----------
def sql_steps(sql):
    s = " ".join(str(sql).split())
    flags = re.IGNORECASE
    steps = []

    tables = []
    for name in re.findall(r'\b(?:FROM|JOIN)\s+["`\[]?(\w+)', s, flags):
        if name not in tables:
            tables.append(name)
    if tables:
        title = "Read tables" if len(tables) > 1 else "Read table"
        steps.append((title, ", ".join(tables)))

    if re.search(r"\bJOIN\b", s, flags):
        steps.append(("Combine the tables", "match rows using JOIN"))

    where = re.search(r"\bWHERE\b(.*?)(?=\bGROUP BY\b|\bORDER BY\b|\bLIMIT\b|$)", s, flags)
    if where and where.group(1).strip():
        steps.append(("Keep only rows where", where.group(1).strip()))

    group = re.search(r"\bGROUP BY\b(.*?)(?=\bHAVING\b|\bORDER BY\b|\bLIMIT\b|$)", s, flags)
    if group and group.group(1).strip():
        steps.append(("Group rows by", group.group(1).strip()))

    names = {"SUM": "total", "AVG": "average", "COUNT": "count", "MIN": "smallest", "MAX": "largest"}
    found = re.findall(r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(", s, flags)
    if found:
        steps.append(("Calculate", ", ".join(sorted({names[f.upper()] for f in found}))))

    having = re.search(r"\bHAVING\b(.*?)(?=\bORDER BY\b|\bLIMIT\b|$)", s, flags)
    if having and having.group(1).strip():
        steps.append(("Keep only groups where", having.group(1).strip()))

    order = re.search(r"\bORDER BY\b(.*?)(?=\bLIMIT\b|$)", s, flags)
    if order and order.group(1).strip():
        steps.append(("Sort by", order.group(1).strip()))

    limit = re.search(r"\bLIMIT\s+(\d+)", s, flags)
    if limit:
        steps.append(("Keep only the first", f"{limit.group(1)} rows"))

    return steps


# ---------- Numbers behind an answer ----------
def key_facts(df, value_col):
    if len(df) < 2:
        return None
    label_col = None
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            label_col = c
            break
    if label_col:
        labels = df[label_col].astype(str)
    else:
        labels = pd.Series([f"Row {i + 1}" for i in range(len(df))], index=df.index)
    values = df[value_col]
    top = values.idxmax()
    low = values.idxmin()
    return {
        "labels": labels,
        "values": values,
        "value_col": value_col,
        "top_label": labels[top],
        "top_value": values[top],
        "low_label": labels[low],
        "low_value": values[low],
        "avg": values.mean(),
        "total": values.sum(),
    }


# ---------- Draws the explanation flow chart ----------
def explain_dot(question, steps, n_rows, n_cols, facts):
    lines = [
        "digraph {",
        '  rankdir=TB; bgcolor="transparent";',
        '  node [shape=box, style="rounded,filled", fontname="Helvetica", fontsize=11, color="#6366f1", fillcolor="#eef2ff", fontcolor="#1e1b4b"];',
        '  edge [color="#8b5cf6"];',
        f'  q [label="Your question\\n{clean_text(question, 70)}", fillcolor="#fef9c3", color="#eab308"];',
        '  ai [label="AI (Gemini) understands it\\nand writes a SQL query"];',
        "  q -> ai;",
    ]
    previous = "ai"
    for i, (title, detail) in enumerate(steps):
        node = f"s{i}"
        shape = "cylinder" if title.startswith("Read table") else "box"
        lines.append(
            f'  {node} [label="{clean_text(title, 40)}\\n{clean_text(detail, 70)}", shape={shape}];'
        )
        lines.append(f"  {previous} -> {node};")
        previous = node

    result_text = f"Result: {n_rows} rows, {n_cols} columns"
    if facts:
        result_text += (
            f"\\nHighest: {short(facts['top_label'])} ({format_number(facts['top_value'])})"
            f"\\nLowest: {short(facts['low_label'])} ({format_number(facts['low_value'])})"
            f"\\nAverage: {format_number(facts['avg'])}"
        )
    lines.append(f'  res [label="{result_text}", fillcolor="#dcfce7", color="#22c55e"];')
    lines.append(f"  {previous} -> res;")
    lines.append(
        '  out [label="AI explains it in a sentence\\nand the app draws grid, chart, stats", fillcolor="#fce7f3", color="#ec4899"];'
    )
    lines.append("  res -> out;")
    lines.append("}")
    return "\n".join(lines)


# ---------- The connector: reads what is inside the database ----------
def get_db_info(db_file):
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    info = {}
    for (table,) in rows:
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        info[table] = {"columns": [(c[1], c[2]) for c in cols], "rows": count}
    conn.close()
    return info


def schema_text(info):
    lines = []
    for table, details in info.items():
        cols = ", ".join(f"{name} {kind}" for name, kind in details["columns"])
        lines.append(f"{table}({cols})")
    return "\n".join(lines)


# ---------- Keeps the AI connection alive; finds the key on laptop or cloud ----------
@st.cache_resource
def get_client():
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        try:
            key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            key = None
    return genai.Client(api_key=key)


# ---------- Creates the AI chat; the notepad "captured" saves every query result ----------
def make_chat(db_file, schema, captured):
    def run_query(sql: str) -> str:
        """Run a read-only SQL SELECT query on the connected database."""
        if not sql.strip().lower().startswith("select"):
            return "Error: only SELECT queries are allowed."
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        try:
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(MAX_ROWS)
            captured.append({"sql": sql, "columns": columns, "rows": rows})
            return f"columns={columns}; rows={rows}"
        except Exception as e:
            return f"Error: {e}"
        finally:
            conn.close()

    return get_client().chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            tools=[run_query],
            system_instruction=(
                "You answer questions using the connected SQLite database. "
                "Use the run_query tool to get data, and answer only from its results. "
                "When the user asks to see, list, compare, summarize or chart data, "
                "run ONE query that returns the relevant rows with clear column names "
                "(use AS to name columns). For totals by group, use JOIN and GROUP BY. "
                "Put the label column first and the number column after it. "
                "Keep your text answer short, because the app shows the table, "
                "chart, statistics and explanation by itself. "
                f"Database structure:\n{schema}"
            ),
        ),
    )


# ---------- The chart tab ----------
def show_chart(df, key):
    num_cols = numeric_columns(df)
    if len(df) < 2 or not num_cols:
        st.caption("A chart needs at least 2 rows and 1 column with numbers.")
        return

    left, right = st.columns(2)
    value_col = left.selectbox("Column to chart", num_cols, key=f"{key}_col")
    kind = right.radio(
        "Chart type", ["Bar", "Line", "Area"], horizontal=True, key=f"{key}_kind"
    )

    label_col = None
    for c in df.columns:
        if not pd.api.types.is_numeric_dtype(df[c]):
            label_col = c
            break

    if label_col:
        chart_df = df.set_index(label_col)[[value_col]]
    else:
        chart_df = df[[value_col]]

    if kind == "Bar":
        st.bar_chart(chart_df)
    elif kind == "Line":
        st.line_chart(chart_df)
    else:
        st.area_chart(chart_df)


# ---------- The statistics tab (also used by the dashboard) ----------
def show_stats(df, key):
    cols = numeric_columns(df)
    if not cols:
        st.caption("No number columns to summarize here.")
        return

    col = st.selectbox("Column to analyze", cols, key=f"{key}_stat")
    s = df[col].dropna()
    if s.empty:
        st.caption("No values to summarize.")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Count", len(s))
    c2.metric("Min", format_number(s.min()))
    c3.metric("Max", format_number(s.max()))
    c4.metric("Average", format_number(s.mean()))
    c5.metric("Median", format_number(s.median()))

    if len(s) >= 3 and s.nunique() > 1:
        counts, edges = np.histogram(s, bins=min(10, len(s)))
        mids = ((edges[:-1] + edges[1:]) / 2).round(2)
        hist = pd.DataFrame({"How many values": counts}, index=mids)
        st.caption(f"Distribution of {col}: how many values fall in each range")
        st.area_chart(hist)

    st.caption("Full statistics table")
    st.dataframe(df[cols].describe().round(2))


# ---------- The explain tab: flow chart + numbers + shares ----------
def show_explain(message, df, key):
    steps = sql_steps(message["result"]["sql"])
    nums = numeric_columns(df)
    facts = None
    if nums and len(df) >= 2:
        value_col = st.selectbox("Numbers to explain", nums, key=f"{key}_xcol")
        facts = key_facts(df, value_col)

    st.markdown("**① The path your question took**")
    st.graphviz_chart(
        explain_dot(message.get("question", ""), steps, len(df), len(df.columns), facts)
    )

    if not facts:
        st.caption("Ask for a list or a comparison (2 or more rows) to see the numbers behind the answer.")
        return

    st.markdown("**② The numbers behind the answer**")
    a, b, c, d = st.columns(4)
    a.metric(f"Highest: {short(facts['top_label'])}", format_number(facts["top_value"]))
    b.metric(f"Lowest: {short(facts['low_label'])}", format_number(facts["low_value"]))
    c.metric("Average", format_number(facts["avg"]))
    d.metric("Total", format_number(facts["total"]))

    values = facts["values"]
    st.markdown("**③ Who contributes how much**")
    if facts["total"] > 0 and values.min() >= 0:
        share = pd.DataFrame(
            {
                "Item": facts["labels"],
                facts["value_col"]: values,
                "Share": values / facts["total"] * 100,
            }
        )
        share = share.sort_values(facts["value_col"], ascending=False)
        st.dataframe(
            share,
            hide_index=True,
            column_config={
                "Share": st.column_config.ProgressColumn(
                    "Share of total", format="%.1f%%", min_value=0, max_value=100
                )
            },
        )
    st.bar_chart(pd.DataFrame({facts["value_col"]: values.values}, index=facts["labels"].values))


# ---------- Shows one answer: grid, chart, stats, explain ----------
def show_results(message, key):
    result = message["result"]
    df = pd.DataFrame(result["rows"], columns=result["columns"])
    if df.empty:
        st.caption("The query returned no rows.")
        return

    if df.shape == (1, 1):
        st.metric(label=str(df.columns[0]), value=str(df.iloc[0, 0]))

    grid_tab, chart_tab, stats_tab, explain_tab = st.tabs(
        ["📋 Grid", "📊 Chart", "📈 Stats", "📖 Explain"]
    )
    with grid_tab:
        st.dataframe(df, hide_index=True)
    with chart_tab:
        show_chart(df, key)
    with stats_tab:
        show_stats(df, key)
    with explain_tab:
        show_explain(message, df, key)


def render_message(message, index):
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("result"):
            show_results(message, f"msg{index}")
        if message.get("sqls"):
            with st.expander("🔎 See the SQL the AI used"):
                for q in message["sqls"]:
                    st.code(q, language="sql")


# ---------- Left panel: Connect form, tables, examples ----------
with st.sidebar:
    st.header("🔌 Connect")
    st.selectbox("Database type", ["SQLite"])
    db_file = st.text_input("Database file name", value="shop.db")

    if st.button("Connect"):
        try:
            info = get_db_info(db_file)
            schema = schema_text(info)
            captured = []
            chat = make_chat(db_file, schema, captured)
            st.session_state.info = info
            st.session_state.schema = schema
            st.session_state.captured = captured
            st.session_state.chat = chat
            st.session_state.db_file = db_file
            st.session_state.messages = []
            st.success("Connected!")
        except Exception as e:
            st.error(f"Could not connect: {e}")

    if "chat" in st.session_state:
        st.divider()
        st.subheader("📚 Tables")
        for table, details in st.session_state.info.items():
            st.markdown(f"**{table}** · {details['rows']} rows")
            st.caption(", ".join(name for name, kind in details["columns"]))

        st.divider()
        st.subheader("💡 Try asking")
        for i, example in enumerate(EXAMPLES):
            if st.button(example, key=f"example{i}"):
                st.session_state.pending = example

        st.divider()
        if st.button("🧹 Clear chat"):
            st.session_state.messages = []
            st.session_state.captured.clear()
            st.session_state.chat = make_chat(
                st.session_state.db_file,
                st.session_state.schema,
                st.session_state.captured,
            )


# ---------- Main area ----------
if "chat" not in st.session_state:
    st.info("👈 Choose a database in the left panel and click Connect.")
    st.stop()

info = st.session_state.info
card1, card2, card3 = st.columns(3)
card1.metric("Database", st.session_state.db_file)
card2.metric("Tables", len(info))
card3.metric("Total rows", sum(d["rows"] for d in info.values()))

with st.expander("🗂️ Browse your tables (grid view)"):
    table = st.selectbox("Choose a table", list(info.keys()), key="browse_table")
    conn = sqlite3.connect(f"file:{st.session_state.db_file}?mode=ro", uri=True)
    st.dataframe(
        pd.read_sql_query(f'SELECT * FROM "{table}" LIMIT 200', conn), hide_index=True
    )
    conn.close()

with st.expander("📈 Statistics dashboard"):
    dash_table = st.selectbox("Table to analyze", list(info.keys()), key="dash_table")
    conn = sqlite3.connect(f"file:{st.session_state.db_file}?mode=ro", uri=True)
    dash_df = pd.read_sql_query(f'SELECT * FROM "{dash_table}" LIMIT 5000', conn)
    conn.close()

    d1, d2, d3 = st.columns(3)
    d1.metric("Rows analyzed", len(dash_df))
    d2.metric("Columns", len(dash_df.columns))
    d3.metric("Missing values", int(dash_df.isna().sum().sum()))

    st.markdown("**Numbers**")
    show_stats(dash_df, "dash")

    text_cols = [c for c in dash_df.columns if not pd.api.types.is_numeric_dtype(dash_df[c])]
    if text_cols:
        st.markdown("**Categories (top 10 most common values)**")
        cat = st.selectbox("Category column", text_cols, key="dash_cat")
        st.bar_chart(dash_df[cat].value_counts().head(10))

with st.expander("🔀 How this app works (flow chart)"):
    st.graphviz_chart(APP_FLOW)

typed = st.chat_input("Ask a question about your data")
pending = st.session_state.pop("pending", None)
question = typed or pending

for i, m in enumerate(st.session_state.messages):
    render_message(m, i)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    render_message(st.session_state.messages[-1], len(st.session_state.messages) - 1)

    st.session_state.captured.clear()
    with st.spinner("Thinking..."):
        try:
            reply = st.session_state.chat.send_message(question)
            answer = reply.text or "I could not produce an answer."
        except Exception as e:
            answer = f"Error: {e}"

    found = list(st.session_state.captured)
    with_rows = [c for c in found if c["rows"]]
    result = with_rows[-1] if with_rows else None

    message = {
        "role": "assistant",
        "content": answer,
        "question": question,
        "result": result,
        "sqls": [c["sql"] for c in found],
    }
    st.session_state.messages.append(message)
    render_message(message, len(st.session_state.messages) - 1)