# DB Chatbot

Chat with a database in plain English. Built with Python, SQLite, Streamlit, and the Gemini API.

## What it does
You open a web page, click Connect to link a database, and ask questions like "Which product is the cheapest?". The AI writes the SQL query, the app runs it on the database, and the AI explains the result in a sentence.

## What is inside
- app.py: the web app with a Connect form and a chat window (main version)
- bot.py: a simple terminal version of the chatbot
- setup_db.py: creates a sample shop database
- shop.db: the sample database (products, prices, stock)
- requirements.txt: the Python tools the app needs

## How to run the web app
1. Install Python.
2. Run: pip install -r requirements.txt
3. Get a free API key from aistudio.google.com
4. Set your key in the terminal (PowerShell): $env:GEMINI_API_KEY="your-key"
5. Run: python -m streamlit run app.py
6. In the page that opens, click Connect, then type a question at the bottom.

The app only reads data. It blocks any request that tries to change the database.

Never put your API key inside the code files.

Built while learning how AI tools and databases work. Uses sample data only.
