# DB Chatbot

Chat with a database in plain English. Built with Python, SQLite, Streamlit, and the Gemini API.

## What it does
Open the web page, click Connect to choose a database, and ask questions like "Total revenue by product category". The AI writes the SQL query, the app runs it (read-only), and you get:
- a short answer
- a grid (table)
- a chart (bar, line, or area)
- statistics (count, min, max, average, median, and a distribution chart)
- an explanation: a flow chart of the steps behind the answer, the key numbers, and each item's share of the total

## What is inside
- app4.py: the main web app
- app.py: the first, simpler web version
- bot.py: a simple terminal version
- setup_db.py: creates a small shop database
- setup_databases.py: creates 4 sample databases (sales, school, hospital, hr)
- requirements.txt: the Python tools the app needs

## How to run
1. Install Python.
2. Run: pip install -r requirements.txt
3. Run: python setup_databases.py
4. Get a free API key from aistudio.google.com
5. Set your key in the terminal (PowerShell): $env:GEMINI_API_KEY="your-key"
6. Run: python -m streamlit run app4.py
7. In the page, type a database file name (for example sales.db), click Connect, and ask a question.

The app only reads data. It blocks any request that tries to change the database.

Never put your API key inside the code files.

Built while learning how AI tools and databases work. Uses sample data only.
