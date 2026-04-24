# THIS IS ASYNC VERSION 
import os
import json
import aiosqlite
import anyio
from fastmcp import FastMCP
from contextlib import asynccontextmanager

# 1. SETUP PATHS
DB_PATH = "file::memory:?cache=shared"
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

# Global database connection (will be set in lifespan)
_db = None

@asynccontextmanager
async def lifespan(app):
    global _db
    # Open a single connection that stays alive for the whole server lifetime
    _db = await aiosqlite.connect(DB_PATH)
    await _db.execute("PRAGMA journal_mode=WAL;")
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            subcategory TEXT,
            note TEXT
        )
    """)
    await _db.commit()
    
    yield  # Server runs here
    
    # Cleanup: close the connection when the server stops
    await _db.close()

# 2. INITIALIZE MCP
mcp = FastMCP("ExpenseTracker", lifespan=lifespan)

# 3. ASYNC TOOLS (using the global connection)
@mcp.tool()
async def add_expense(date: str, amount: float, category: str, subcategory: str = None, note: str = None) -> str:
    """Add a new expense entry to the database asynchronously."""
    global _db
    await _db.execute("""
        INSERT INTO expenses (date, amount, category, subcategory, note)
        VALUES (?, ?, ?, ?, ?)
    """, (date, amount, category, subcategory, note))
    await _db.commit()
    return f"Expense of ₹{amount} added successfully on {date}"

@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> str:
    """List expenses within a given date range (YYYY-MM-DD)."""
    global _db
    _db.row_factory = aiosqlite.Row
    async with _db.execute("""
        SELECT id, date, amount, category, subcategory, note 
        FROM expenses 
        WHERE date BETWEEN ? AND ? 
        ORDER BY date ASC
    """, (start_date, end_date)) as cursor:
        rows = await cursor.fetchall()
    
    if not rows:
        return f"No expenses found between {start_date} and {end_date}."
    
    result = f"Expenses from {start_date} to {end_date}:\n\n"
    result += "Date | Amount | Category | Subcategory | Note\n"
    result += "-" * 60 + "\n"
    for row in rows:
        result += f"{row['date']} | ₹{row['amount']} | {row['category']} | {row['subcategory'] or ''} | {row['note'] or ''}\n"
    
    total = sum(row['amount'] for row in rows)
    result += f"\nTotal: ₹{total}"
    return result

@mcp.tool()
async def summarize_expenses(start_date: str, end_date: str, category: str = None) -> str:
    """Get total expense within a date range, optionally filtered by category."""
    global _db
    if category:
        query = "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ? AND category = ?"
        params = (start_date, end_date, category)
    else:
        query = "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?"
        params = (start_date, end_date)
        
    async with _db.execute(query, params) as cursor:
        row = await cursor.fetchone()
        total = row[0] if row[0] is not None else 0
    
    return f"Total expense {'for ' + category if category else ''} from {start_date} to {end_date}: ₹{total}"

# 4. ASYNC RESOURCES
@mcp.resource("expenses://categories", mime_type="application/json")
async def get_categories() -> str:
    default = {"categories": ["Food", "Transport", "Bills"]}
    try:
        path = anyio.Path(CATEGORIES_PATH)
        if await path.exists():
            content = await path.read_text()
            # Validate JSON
            if json.loads(content):
                return content
        return json.dumps(default)
    except Exception:
        return json.dumps(default)

# 5. RUN SERVER (commented out because FastMCP Cloud runs it automatically)
# if __name__ == "__main__":
#     mcp.run(transport="http", host="0.0.0.0", port=8000)