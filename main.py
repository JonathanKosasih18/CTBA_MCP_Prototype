import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Import FastMCP
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("CBTA MCP Proto")

# MySQL Database Connection
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# === MCP Server Tools ===

@mcp.tool()
def fetch_raw_transaction_data():
    """
    Fetch the raw, unstandardized transaction counts grouped by the salesman_name column.
    This provides the messy data needed for AI-driven standardization.
    """
    query = text("""
        SELECT 
            salesman_name, 
            COUNT(*) as transaction_count 
        FROM transactions 
        GROUP BY salesman_name
    """)
    
    with engine.connect() as connection:
        result = connection.execute(query)
        return [
            {"raw_name": row.salesman_name, "count": row.transaction_count} 
            for row in result
        ]

@mcp.prompt()
def generate_cleaned_sales_report() -> str:
    """
    Instructions for the AI to fetch raw data, standardize salesperson names,
    and aggregate counts for a final performance report.
    """
    raw_data = fetch_raw_transaction_data()

    return f"""
    I need a standardized Sales Performance Report. The database contains messy entries.
    
    DATA TO ANALYZE:
    {raw_data}

    YOUR LOGIC REQUIREMENTS:
    1. **Normalize Names**: Group similar names (e.g., 'GLADYS', 'PS100 Gladys', 'PS 100 Gladys' should all be 'GLADYS'). Remove numeric codes like '310' or '214'.
    2. **Handle Multi-Salesman Entries**: For entries like 'GLADY / WILSON', split the transaction count and add the full amount to BOTH individuals.
    3. **Consistency**: Use uppercase for all final names.
    
    OUTPUT FORMAT:
    Provide a Markdown table with columns: [Salesperson, Total Transactions].
    Include a summary of which raw names were merged into which standardized names.
    """

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")