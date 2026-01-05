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
def fetch_salesperson_transactions_count():
    """
    Fetch the count of transactions per salesperson.
    Returns a list of dictionaries containing salesperson names and their total transaction counts.
    """
    # We group by salesman_name to aggregate the data
    query = text("""
        SELECT 
            salesman_name, 
            COUNT(*) as transaction_count 
        FROM transactions 
        GROUP BY salesman_name
        ORDER BY transaction_count DESC
    """)
    
    with engine.connect() as connection:
        result = connection.execute(query)
        # Convert the result rows into a list of dictionaries for the MCP response
        data = [
            {"salesman_name": row.salesman_name, "count": row.transaction_count} 
            for row in result
        ]
    
    return data



# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")