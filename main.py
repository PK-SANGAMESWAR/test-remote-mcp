import os
import json
import aiosqlite
from fastmcp import FastMCP
import asyncio

BASE_DIR = os.path.dirname(__file__) or "."
DB_PATH = os.path.join(BASE_DIR, "expenses_async.db")
CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("ExpenseTracker")


# ----------------------------
# INITIALIZE DATABASE (ASYNC)
# ----------------------------
async def init_db():
    """Initialize the DB and required tables asynchronously."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                credit REAL DEFAULT 0
            )
        """)

        # Ensure default user exists
        await conn.execute(
            "INSERT OR IGNORE INTO users (name, credit) VALUES (?, ?)",
            ("default", 0.0)
        )

        # Indexes
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON expenses(date)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_cat ON expenses(category)")

        await conn.commit()


# Run DB init on startup
asyncio.run(init_db())


# ----------------------------
# ADD EXPENSE
# ----------------------------
@mcp.tool()
async def add_expense(date, amount, category, subcategory="", note=""):
    """Add new expense (ASYNC)."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cur = await conn.execute(
                """
                INSERT INTO expenses (date, amount, category, subcategory, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (date, float(amount), category, subcategory, note)
            )
            await conn.commit()
            return {"status": "ok", "id": cur.lastrowid}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# LIST EXPENSES
# ----------------------------
@mcp.tool()
async def list_expenses(start_date, end_date):
    """List expenses between dates (ASYNC)."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cur = await conn.execute(
                """
                SELECT id, date, amount, category, subcategory, note
                FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC, id DESC
                """,
                (start_date, end_date)
            )
            rows = await cur.fetchall()
            cols = [c[0] for c in cur.description]
            return {"status": "ok", "expenses": [dict(zip(cols, r)) for r in rows]}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# SUMMARIZE EXPENSES
# ----------------------------
@mcp.tool()
async def summarize(start_date, end_date, category=None):
    """Summarize expenses (ASYNC)."""
    try:
        params = [start_date, end_date]
        query = """
            SELECT category, SUM(amount) AS total_amount, COUNT(*) AS count
            FROM expenses
            WHERE date BETWEEN ? AND ?
        """

        if category:
            query += " AND category = ?"
            params.append(category)

        query += " GROUP BY category ORDER BY total_amount DESC"

        async with aiosqlite.connect(DB_PATH) as conn:
            cur = await conn.execute(query, params)
            rows = await cur.fetchall()
            cols = [c[0] for c in cur.description]
            return {"status": "ok", "summary": [dict(zip(cols, r)) for r in rows]}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# EDIT EXPENSE
# ----------------------------
@mcp.tool()
async def edit_expense(id, date, amount, category, subcategory="", note=""):
    """Edit expense by ID (ASYNC)."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cur = await conn.execute(
                """
                UPDATE expenses
                SET date=?, amount=?, category=?, subcategory=?, note=?
                WHERE id=?
                """,
                (date, float(amount), category, subcategory, note, id)
            )
            await conn.commit()

            if cur.rowcount == 0:
                return {"status": "error", "error": "ID not found"}

            return {"status": "ok"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# DELETE EXPENSE
# ----------------------------
@mcp.tool()
async def delete_expense(id):
    """Delete expense by ID (ASYNC)."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            cur = await conn.execute("DELETE FROM expenses WHERE id=?", (id,))
            await conn.commit()

            if cur.rowcount == 0:
                return {"status": "error", "error": "ID not found"}

            return {"status": "ok"}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# ADD CREDIT
# ----------------------------
@mcp.tool()
async def add_credit(amount, user_name="default"):
    """Add credit to a user's wallet (ASYNC)."""
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO users (name, credit) VALUES (?, ?)",
                (user_name, 0.0)
            )
            await conn.execute(
                "UPDATE users SET credit = credit + ? WHERE name = ?",
                (float(amount), user_name)
            )
            cur = await conn.execute("SELECT credit FROM users WHERE name=?", (user_name,))
            row = await cur.fetchone()
            await conn.commit()

            return {"status": "ok", "credit": row[0]}

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ----------------------------
# RESOURCE: CATEGORIES.JSON
# ----------------------------
@mcp.resource("expense://categories", mime_type="application/json")
def categories():
    """Returns categories.json or default categories."""
    try:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return json.dumps({
            "categories": [
                "Food", "Transportation", "Shopping", "Entertainment",
                "Bills", "Healthcare", "Travel", "Education", "Business", "Other"
            ]
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ----------------------------
# START MCP SERVER
# ----------------------------
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)

