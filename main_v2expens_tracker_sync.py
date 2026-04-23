from fastmcp import FastMCP
import sqlite3
import os
import json
# Create database connection
# DB_PATH = "expenses.db"
DB_PATH = os.path.join(os.path.dirname(__file__), "expenses.db")
CATEGORIES_PATH = os.path.join(os.path.dirname(__file__), "categories.json")
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("ExpenseTracker")

def init_db():
    """Initialize the database table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT,
            subcategory TEXT,
            note TEXT
        )
    """)
    conn.commit()
    conn.close()

# Initialize database when server starts
init_db()


mcp = FastMCP(name="Demo Server")
@mcp.tool()
def add_expense(date: str, amount: float, category: str, subcategory: str = None, note: str = None) -> str:
    """Add a new expense entry to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO expenses (date, amount, category, subcategory, note)
        VALUES (?, ?, ?, ?, ?)
    """, (date, amount, category, subcategory, note))
    conn.commit()
    conn.close()
    return f"Expense of ₹{amount} added successfully on {date}"

@mcp.tool()
def list_expenses(start_date: str, end_date: str) -> str:
    """List expenses within a given date range (YYYY-MM-DD)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, amount, category, subcategory, note 
        FROM expenses 
        WHERE date BETWEEN ? AND ? 
        ORDER BY date ASC
    """, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return f"No expenses found between {start_date} and {end_date}."
    
    result = f"Expenses from {start_date} to {end_date}:\n\n"
    result += "Date | Amount | Category | Subcategory | Note\n"
    result += "-" * 50 + "\n"
    for row in rows:
        result += f"{row[1]} | ₹{row[2]} | {row[3]} | {row[4]} | {row[5]}\n"
    
    total = sum(row[2] for row in rows)
    result += f"\nTotal: ₹{total}"
    return result


@mcp.tool()
def summarize_expenses(start_date: str, end_date: str, category: str = None) -> str:
    """Get total expense within a date range, optionally filtered by category."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if category:
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE date BETWEEN ? AND ? AND category = ?
        """, (start_date, end_date, category))
    else:
        cursor.execute("""
            SELECT SUM(amount) FROM expenses 
            WHERE date BETWEEN ? AND ?
        """, (start_date, end_date))
    
    total = cursor.fetchone()[0]
    conn.close()
    
    if total is None:
        total = 0
    
    if category:
        return f"Total expense on {category} from {start_date} to {end_date}: ₹{total}"
    else:
        return f"Total expense from {start_date} to {end_date}: ₹{total}"

@mcp.resource("expenses://categories", mime_type="application/json")
def get_categories() -> str:
    """Return the list of valid categories and subcategories."""
    with open(CATEGORIES_PATH, "r") as f: 
        return f.read()

# Run the server with HTTP transport
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
