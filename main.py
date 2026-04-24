# ASYNC EXPENSE TRACKER MCP SERVER – FIXED FOR FASTCLOUD
import os
import json
import aiosqlite
import anyio
from fastmcp import FastMCP
from contextlib import asynccontextmanager

# ------------------------------------------------------------------
# 1. DATABASE PATH – SHARED IN-MEMORY (survives across connections)
# ------------------------------------------------------------------
DB_PATH = "file::memory:?cache=shared"

# ------------------------------------------------------------------
# 2. LIFESPAN – OPEN PERSISTENT CONNECTION AND ENSURE TABLE EXISTS
# ------------------------------------------------------------------
_db_connection = None

@asynccontextmanager
async def lifespan(app):
    global _db_connection
    # Create a connection that stays alive for the whole server lifetime
    _db_connection = await aiosqlite.connect(DB_PATH)
    await _db_connection.execute("PRAGMA journal_mode=WAL")
    await _db_connection.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            subcategory TEXT,
            note TEXT
        )
    """)
    await _db_connection.commit()
    
    yield  # server runs here
    
    # Clean shutdown
    await _db_connection.close()

mcp = FastMCP("ExpenseTracker", lifespan=lifespan)

# ------------------------------------------------------------------
# 3. HELPER TO GET THE GLOBAL CONNECTION (with safety check)
# ------------------------------------------------------------------
async def get_db():
    global _db_connection
    if _db_connection is None:
        # Fallback: create a new connection (shouldn't happen if lifespan works)
        conn = await aiosqlite.connect(DB_PATH)
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                subcategory TEXT,
                note TEXT
            )
        """)
        await conn.commit()
        return conn
    return _db_connection

# ------------------------------------------------------------------
# 4. TOOLS – each uses the same persistent connection
# ------------------------------------------------------------------
@mcp.tool()
async def add_expense(date: str, amount: float, category: str, subcategory: str = None, note: str = None) -> str:
    """Add a new expense."""
    db = await get_db()
    await db.execute(
        "INSERT INTO expenses (date, amount, category, subcategory, note) VALUES (?, ?, ?, ?, ?)",
        (date, amount, category, subcategory, note)
    )
    await db.commit()
    return f"✅ Expense of ₹{amount} added on {date}"

@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> str:
    """List expenses between two dates (YYYY-MM-DD)."""
    db = await get_db()
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT date, amount, category, subcategory, note FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date",
        (start_date, end_date)
    ) as cursor:
        rows = await cursor.fetchall()
    
    if not rows:
        return f"No expenses from {start_date} to {end_date}."
    
    output = f"📋 Expenses {start_date} → {end_date}:\n\n"
    output += "Date       | Amount | Category     | Note\n"
    output += "-" * 50 + "\n"
    for r in rows:
        output += f"{r['date']} | ₹{r['amount']} | {r['category']:12} | {r['note'] or ''}\n"
    total = sum(r['amount'] for r in rows)
    output += f"\n💰 Total: ₹{total}"
    return output

@mcp.tool()
async def summarize_expenses(start_date: str, end_date: str, category: str = None) -> str:
    """Total expenses for a period, optionally filtered by category."""
    db = await get_db()
    if category:
        async with db.execute(
            "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ? AND category = ?",
            (start_date, end_date, category)
        ) as cur:
            total = (await cur.fetchone())[0] or 0
        return f"📊 Total {category} expenses {start_date}–{end_date}: ₹{total}"
    else:
        async with db.execute(
            "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?",
            (start_date, end_date)
        ) as cur:
            total = (await cur.fetchone())[0] or 0
        return f"📊 Total expenses {start_date}–{end_date}: ₹{total}"

# ------------------------------------------------------------------
# 5. RESOURCE – categories (fallback if file missing)
# ------------------------------------------------------------------
@mcp.resource("expenses://categories", mime_type="application/json")
async def get_categories() -> str:
    default = {
        "categories": ["Food", "Transport", "Bills", "Entertainment", "Shopping", "Health"]
    }
    try:
        path = anyio.Path(CATEGORIES_PATH)
        if await path.exists():
            content = await path.read_text()
            # Validate JSON
            json.loads(content)
            return content
    except Exception:
        pass
    return json.dumps(default)

# ------------------------------------------------------------------
# 6. (Optional) Health check tool for debugging
# ------------------------------------------------------------------
@mcp.tool()
async def health_check() -> str:
    """Check if the database is accessible."""
    try:
        db = await get_db()
        await db.execute("SELECT 1")
        return "✅ Server healthy, database ready"
    except Exception as e:
        return f"❌ Database error: {e}"

# ------------------------------------------------------------------
# 7. RUN – fastmcp cloud will handle this automatically
# ------------------------------------------------------------------
# if __name__ == "__main__":
#     mcp.run(transport="http", host="0.0.0.0", port=8000)