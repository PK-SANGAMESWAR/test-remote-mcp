import os
import sqlite3
import random
from fastmcp import FastMCP

# Paths
BASE_DIR = os.path.dirname(__file__) or "."
DB_PATH = os.path.join(BASE_DIR, "expenses.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")  # removed stray spaces

mcp = FastMCP(name="ExpenseTracker")


def init_db():
    """Initialize the DB and required tables."""
    # ensure directory exists (usually __file__ directory exists)
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )
        """)
        # Optional users table for credit operations
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            credit REAL DEFAULT 0
        )
        """)
        # ensure at least one user exists so add_credit works
        cursor.execute("SELECT id FROM users LIMIT 1")
        if cursor.fetchone() is None:
            cursor.execute("INSERT INTO users (name, credit) VALUES (?, ?)", ("default", 0.0))

        # index for queries by date/category (optional but helpful)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category)")


init_db()


## ADD EXPENSE
@mcp.tool()
def add_expense(date, amount, category, subcategory="", note=""):
    """Add a new expense to the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO expenses (date, amount, category, subcategory, note)
            VALUES (?, ?, ?, ?, ?)
            """, (date, float(amount), category, subcategory, note))
            return {"status": "ok", "id": cursor.lastrowid}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## LIST EXPENSES
@mcp.tool()
def list_expenses(start_date, end_date):
    """List all expenses in the database between start_date and end_date (inclusive)."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, date, amount, category, subcategory, note FROM expenses WHERE date BETWEEN ? AND ? ORDER BY id ASC",
                (start_date, end_date)
            )
            cols = [desc[0] for desc in cursor.description]
            return {"status": "ok", "expenses": [dict(zip(cols, row)) for row in cursor.fetchall()]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## SUMMARIZE
@mcp.tool()
def summarize(start_date, end_date, category=None):
    """
    Summarize expenses by category within the inclusive date range.
    Returns list of {"category": ..., "total": ...} ordered by total descending.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            params = [start_date, end_date]
            query = """
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE date BETWEEN ? AND ?
            """
            if category:
                query += " AND category = ?"
                params.append(category)

            query += " GROUP BY category ORDER BY total DESC"
            cursor = conn.cursor()
            cursor.execute(query, params)
            cols = [desc[0] for desc in cursor.description]
            return {"status": "ok", "summary": [dict(zip(cols, row)) for row in cursor.fetchall()]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## EDIT EXPENSE
@mcp.tool()
def edit_expense(id, date, amount, category, subcategory="", note=""):
    """Edit an existing expense in the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE expenses
            SET date = ?, amount = ?, category = ?, subcategory = ?, note = ?
            WHERE id = ?
            """, (date, float(amount), category, subcategory, note, id))
            if cursor.rowcount == 0:
                return {"status": "error", "error": "No expense with that id"}
            return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## DELETE EXPENSE
@mcp.tool()
def delete_expense(id):
    """Delete an expense from the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM expenses WHERE id = ?", (id,))
            if cursor.rowcount == 0:
                return {"status": "error", "error": "No expense with that id"}
            return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## ADD CREDIT
@mcp.tool()
def add_credit(amount, user_name="default"):
    """
    Add credit to the user's account. By default updates 'default' user.
    Returns new credit amount.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # ensure user exists
            cursor.execute("INSERT OR IGNORE INTO users (name, credit) VALUES (?, ?)", (user_name, 0.0))
            cursor.execute("UPDATE users SET credit = credit + ? WHERE name = ?", (float(amount), user_name))
            cursor.execute("SELECT credit FROM users WHERE name = ?", (user_name,))
            new_credit = cursor.fetchone()[0]
            return {"status": "ok", "credit": new_credit}
    except Exception as e:
        return {"status": "error", "error": str(e)}


## Resource: categories (JSON)
@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return '{"error":"categories file not found"}'
    except Exception as e:
        return f'{{"error":"{str(e)}"}}'


if __name__ == "__main__":
    mcp.run()

if __name__ == "__main__":
    mcp.run(transport="http",host="0.0.0.0",port=8000)
    
