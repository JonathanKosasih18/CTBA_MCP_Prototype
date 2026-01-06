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

# === MCP RESOURCES (Static Reference Data) ===

@mcp.resource("sales://official_products")
def get_official_product_list() -> str:
    """
    Retrieves the authoritative list of valid product names from the database.
    
    Acts as the 'Source of Truth' for product normalization tasks.

    Returns:
        str: A formatted, newline-separated string listing all official product names.
             
             Format:
             OFFICIAL PRODUCT REGISTRY:
             - Product A
             - Product B
    """
    query = text("SELECT prodname FROM products")
    with engine.connect() as conn:
        result = conn.execute(query)
        return "OFFICIAL PRODUCT REGISTRY:\n" + "\n".join([f"- {row.prodname}" for row in result])

@mcp.resource("users://official_directory")
def get_official_user_list() -> str:
    """
    Retrieves the official registry of salesmen, including internal ID, Username (unique ID), and Full Name.
    
    Used to resolve identity for messy names or ID-based foreign keys (like 'plans.userid').

    Returns:
        str: A formatted string linking Internal IDs and Usernames to Names.
             
             Format:
             OFFICIAL USER DIRECTORY:
             - [ID: 1] [PS101] John Doe
             - [ID: 2] [PS102] Jane Smith
    """
    query = text("SELECT id, username, name FROM users")
    with engine.connect() as conn:
        result = conn.execute(query)
        return "OFFICIAL USER DIRECTORY:\n" + "\n".join([f"- [ID: {row.id}] [{row.username}] {row.name}" for row in result])

# === MCP TOOLS (Dynamic Data Fetching) ===

@mcp.tool()
def fetch_raw_transaction_data_by_salesman_name() -> str:
    """
    Retrieves a snapshot of unstandardized transaction counts grouped by the raw salesman name.

    Returns:
        str: A formatted log of raw names and their transaction counts.
             
             Format:
             RAW SALES LOG:
             - messy_name_1: 5
             - MESSY NAME 2: 12
    """
    query = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
    with engine.connect() as conn:
        result = conn.execute(query)
        return "RAW SALES LOG:\n" + "\n".join([f"- {row.salesman_name}: {row.c}" for row in result])

@mcp.tool()
def fetch_raw_transaction_data_by_product_name() -> str:
    """
    Retrieves a snapshot of unstandardized transaction counts grouped by the raw product name.

    Returns:
        str: A formatted log of raw product names and their transaction counts.
             
             Format:
             RAW PRODUCT LOG:
             - raw_product_name_a: 8
             - raw_product_name_b: 3
    """
    query = text("SELECT product, COUNT(*) as c FROM transactions GROUP BY product")
    with engine.connect() as conn:
        result = conn.execute(query)
        return "RAW PRODUCT LOG:\n" + "\n".join([f"- {row.product}: {row.c}" for row in result])

@mcp.tool()
def fetch_raw_visit_plans() -> str:
    """
    Retrieves a count of planned visits grouped by the User ID.

    Returns:
        str: A formatted log of User IDs and their plan counts.
             
             Format:
             RAW PLAN LOG:
             - UserID 1: 5 visits
             - UserID 24: 12 visits
    """
    query = text("SELECT userid, COUNT(*) as c FROM plans GROUP BY userid")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        return "RAW PLAN LOG:\n" + "\n".join([f"- UserID {row.userid}: {row.c} visits" for row in result])

# === MCP PROMPTS (Agent Instructions) ===

@mcp.prompt()
def generate_cleaned_sales_report_by_salesman_name() -> str:
    """
    Generates a prompt designed to reconcile messy salesman names against the official directory.
    
    Injects:
    1. `users://official_directory` (Resource) as the dictionary.
    2. `fetch_raw_transaction_data_by_salesman_name` (Tool) as the dirty data.

    Returns:
        str: A fully constructed prompt instructing the LLM to map raw names to official IDs 
             and output a clean Markdown report.
    """
    raw_data = fetch_raw_transaction_data_by_salesman_name()
    official_users = get_official_user_list() 

    return f"""
    I need a standardized Sales Performance Report.
    
    REFERENCE DATA (Source of Truth):
    {official_users}

    RAW DATA TO ANALYZE:
    {raw_data}

    YOUR LOGIC REQUIREMENTS:
    1. **Normalize Names**: Map every raw name to the correct 'Official User' from the directory.
       - Example: 'PS100 Gladys' -> 'Gladys' (or keep the ID if preferred).
    2. **Handle Multi-Salesman Entries**: For 'GLADY / WILSON', credit both 'Gladys' and 'Wilson' by adding the transaction count to each. Do not split the count, instead duplicate it. An entry with N salesmen counts as N separate full credits.
    3. **Consistency**: Use the spelling from the Official Directory.
    
    OUTPUT FORMAT:
    Markdown table: [Official Name, Total Transactions]
    """

@mcp.prompt()
def validate_salesmen_identity() -> str:
    """
    Generates a QA prompt to audit the mapping between raw transaction names and official users.
    
    Useful for detecting new, unknown, or typo-heavy names that the automatic report might miss.

    Returns:
        str: A prompt instructing the LLM to create a 'Validation Table' showing the status 
             (Matched/Unmatched) of every raw name found in the logs.
    """
    raw_data = fetch_raw_transaction_data_by_salesman_name()
    official_users = get_official_user_list()

    return f"""
    Act as a Data Quality Analyst. Map 'Transaction Names' to 'Official Users'.
    
    OFFICIAL DIRECTORY:
    {official_users}

    RAW TRANSACTION NAMES:
    {raw_data}

    YOUR TASK:
    1. **Identify Matches**: Link every raw name to a `[Code] Name` from the directory.
       - Use the Code (e.g. PS100) if present in the raw string.
       - Use Fuzzy Matching on the name if no code is present.
    2. **Flag Anomalies**: List names that have NO match in the directory.

    OUTPUT:
    Validation Report table:
    | Raw Name | Status | Matched Official ID | Matched Official Name |
    """

@mcp.prompt()
def generate_cleaned_product_report() -> str:
    """
    Generates a prompt designed to reconcile raw 'product_names' against the official product registry.

    Injects:
    1. `sales://official_products` (Resource) as the dictionary.
    2. `fetch_raw_transaction_data_by_product_name` (Tool) as the dirty data.

    Returns:
        str: A fully constructed prompt instructing the LLM to map raw products to 
             official product names and aggregate the counts.
    """
    raw_data = fetch_raw_transaction_data_by_product_name()
    official_products = get_official_product_list()

    return f"""
    I need a standardized Product Sales Report.
    
    ### REFERENCE DATA (The Source of Truth)
    Use this list to validate the raw names. If a raw name looks like one of these, map it here.
    {official_products}

    ### RAW DATA TO ANALYZE
    {raw_data}

    ### YOUR LOGIC REQUIREMENTS:
    1. **Normalize Product Names**: Map every 'raw_product_name' from the raw data to the closest match in the 'Official Product Registry'.
    2. **Consolidate Counts**: If multiple raw names map to the same official product, sum their transaction counts.
    3. **Handle Unknowns**: If a raw name does not resemble ANY official product, label it as "Uncategorized".
    
    ### OUTPUT FORMAT:
    Provide a Markdown table with columns: 
    | Official Product Name | Total Transactions |
    """

@mcp.prompt()
def generate_planned_visits_report() -> str:
    """
    Generates a report showing planned visits per salesperson.
    
    Logic:
    1. Fetches raw plan counts (which use 'userid' integers).
    2. Fetches the Official User List (which maps 'id' to 'Name').
    3. Maps the IDs and aggregates the table.

    Returns:
        str: A prompt constructing the 'Planned Visits' markdown table.
    """
    raw_plans = fetch_raw_visit_plans()
    official_users = get_official_user_list()

    return f"""
    I need a Planned Visits Report grouped by Salesperson.
    
    REFERENCE DATA (User Directory):
    {official_users}

    RAW DATA (Plan Counts by User ID):
    {raw_plans}

    YOUR LOGIC REQUIREMENTS:
    1. **Map IDs to Names**: The Raw Data uses 'UserID' (integers). Look up each UserID in the 'REFERENCE DATA' to find the matching Name.
       - Example: If Raw Data has 'UserID 5' and Reference has '- [ID: 5] [PS100] Gladys', map it to 'Gladys'.
    2. **Handle Unmatched IDs**: If a UserID exists in plans but not in the directory, label the name as "Unknown User (ID: X)".
    
    OUTPUT FORMAT:
    Provide a Markdown table with columns: 
    | Salesperson Name | Total Planned Visits |
    """

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")