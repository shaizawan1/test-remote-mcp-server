# THIS IS ASYNC VERSION 
import os
import json
import aiosqlite
import anyio
from fastmcp import FastMCP
import tempfile
from contextlib import asynccontextmanager 

# 1. SETUP PATHS
DB_PATH = os.path.join(tempfile.gettempdir(), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")

@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield

# 2. INITIALIZE MCP
mcp = FastMCP("ExpenseTracker", lifespan=lifespan)

# 3. ASYNC DATABASE INITIALIZATION
async def init_db():
    """Initialize the database table and enable WAL mode for concurrent access."""
    async with aiosqlite.connect(DB_PATH) as db:
        # WAL mode is critical for preventing 'database is locked' errors
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT,
                subcategory TEXT,
                note TEXT
            )
        """)
        await db.commit()


# 4. ASYNC TOOLS
@mcp.tool()
async def add_expense(date: str, amount: float, category: str, subcategory: str = None, note: str = None) -> str:
    """Add a new expense entry to the database asynchronously."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO expenses (date, amount, category, subcategory, note)
            VALUES (?, ?, ?, ?, ?)
        """, (date, amount, category, subcategory, note))
        await db.commit()
    return f"Expense of ₹{amount} added successfully on {date}"

@mcp.tool()
async def list_expenses(start_date: str, end_date: str) -> str:
    """List expenses within a given date range (YYYY-MM-DD)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
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
    async with aiosqlite.connect(DB_PATH) as db:
        if category:
            query = "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ? AND category = ?"
            params = (start_date, end_date, category)
        else:
            query = "SELECT SUM(amount) FROM expenses WHERE date BETWEEN ? AND ?"
            params = (start_date, end_date)
            
        async with db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            total = row[0] if row[0] is not None else 0
    
    return f"Total expense {'for ' + category if category else ''} from {start_date} to {end_date}: ₹{total}"

# 5. ASYNC RESOURCES
@mcp.resource("expenses://categories", mime_type="application/json")
async def get_categories() -> str:
    """Return the list of valid categories and subcategories using async file reading."""
    # anyio.Path allows for non-blocking file I/O
    path = anyio.Path(CATEGORIES_PATH)
    return await path.read_text()

# 6. RUN SERVER
# if __name__ == "__main__":
#     mcp.run(transport="http", host="0.0.0.0", port=8000)