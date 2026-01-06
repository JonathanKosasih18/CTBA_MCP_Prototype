import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Import FastMCP
from mcp.server.fastmcp import FastMCP

# Load environment variables
load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("CTBA MCP Proto")

# MySQL Database Connection
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# === MCP RESOURCES (Static Reference Data) ===

# PRODUCTS RESOURCE
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

# USERS RESOURCE
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

# CLINICS RESOURCE
@mcp.resource("clinics://official_registry")
def get_official_clinic_list() -> str:
    """
    Retrieves the official registry of clinics with detailed location data.
    
    Includes Address, City, and Province to help the AI distinguish between different branches of the same clinic vs. duplicate entries of the same location.

    Returns:
        str: A formatted string linking IDs to Name and Location.
            
            Format:
            OFFICIAL CLINIC REGISTRY:
            - [ID: 1] Name: Klinik Alpha | Loc: Jl. Merdeka, City: JKT, Prov: DKI
            - [ID: 2] Name: Klinik Alpha | Loc: Jl. Sudirman, City: BDG, Prov: JBR
    """
    # Added address, citycode, provcode
    query = text("SELECT id, clinicname, address, citycode, provcode FROM clinics")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        # Format the location data into a "signature" for the AI to analyze
        return "OFFICIAL CLINIC REGISTRY:\n" + "\n".join([
            f"- [ID: {row.id}] Name: {row.clinicname} | Loc: {row.address}, City: {row.citycode}, Prov: {row.provcode}" 
            for row in result
        ])

# CUSTOMERS RESOURCE
@mcp.resource("customers://official_registry")
def get_official_customer_list() -> str:
    """
    Retrieves the official registry of customers with phone contact data.
    
    Includes Phone Numbers to help the AI distinguish between different people with the same name, or merge duplicate entries for the same person.

    Returns:
        str: A formatted string linking IDs to Name and Phone.
            
            Format:
            OFFICIAL CUSTOMER REGISTRY:
            - [ID: 501] Name: John Doe | Phone: 08123456789
            - [ID: 502] Name: John Doe | Phone: 08999999999 (Different Person)
    """
    # specific columns requested: id, custname, phone
    query = text("SELECT id, custname, phone FROM customers")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        # Format the identity signature for the AI
        return "OFFICIAL CUSTOMER REGISTRY:\n" + "\n".join([
            f"- [ID: {row.id}] Name: {row.custname} | Phone: {row.phone}" 
            for row in result
        ])

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

@mcp.tool()
def fetch_raw_visit_plans_by_clinic() -> str:
    """
    Retrieves a snapshot of planned visits grouped by the Clinic ID (foreign key).

    Returns:
        str: A formatted log of Clinic IDs and their plan counts.
            
            Format:
            RAW CLINIC VISIT LOG:
            - ClinicID 101: 5 visits
    """
    query = text("SELECT cliniccode, COUNT(*) as c FROM plans GROUP BY cliniccode")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        return "RAW CLINIC VISIT LOG:\n" + "\n".join([f"- ClinicID {row.cliniccode}: {row.c} visits" for row in result])

@mcp.tool()
def fetch_raw_visit_plans_by_customer() -> str:
    """
    Retrieves a snapshot of planned visits grouped by the Customer ID (foreign key).

    Returns:
        str: A formatted log of Customer IDs and their plan counts.
            
            Format:
            RAW CUSTOMER VISIT LOG:
            - CustID 501: 3 visits
    """
    query = text("SELECT custcode, COUNT(*) as c FROM plans GROUP BY custcode")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        return "RAW CUSTOMER VISIT LOG:\n" + "\n".join([f"- CustID {row.custcode}: {row.c} visits" for row in result])

# === MCP PROMPTS (Agent Instructions) ===

@mcp.prompt()
def generate_cleaned_sales_report_by_salesman_name() -> str:
    """
    Generates a prompt designed to reconcile messy salesman names against the official directory.
    
    Injects:
    1. `users://official_directory` (Resource) as the dictionary.
    2. `fetch_raw_transaction_data_by_salesman_name` (Tool) as the dirty data.

    Returns:
        str: A fully constructed prompt instructing the LLM to map raw names to official IDs and output a clean Markdown report.
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
    1. **Normalize Names**: Map every raw name to the correct 'Official User' from the directory. Example: 'PS100 Gladys' -> 'Gladys' (or keep the ID if preferred).
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
        str: A prompt instructing the LLM to create a 'Validation Table' showing the status (Matched/Unmatched) of every raw name found in the logs.
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
        str: A fully constructed prompt instructing the LLM to map raw products to official product names and aggregate the counts.
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
def generate_planned_visits_report_by_sales() -> str:
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
    1. **Map IDs to Names**: The Raw Data uses 'UserID' (integers). Look up each UserID in the 'REFERENCE DATA' to find the matching Name. Example: If Raw Data has 'UserID 5' and Reference has '- [ID: 5] [PS100] Gladys', map it to 'Gladys'.
    2. **Handle Unmatched IDs**: If a UserID exists in plans but not in the directory, label the name as "Unknown User (ID: X)".
    
    OUTPUT FORMAT:
    Provide a Markdown table with columns: 
    | Salesperson Name | Total Planned Visits |
    """

@mcp.prompt()
def generate_planned_visits_report_by_clinic() -> str:
    """
    Generates a smart report of planned visits that merges duplicate clinic entries 
    while distinguishing different branches.

    Injects:
    1. `clinics://official_registry` (Resource) containing Name + Location Data.
    2. `fetch_raw_visit_plans_by_clinic` (Tool) containing raw counts by ID.

    Returns:
        str: A prompt instructing the AI to perform entity resolution and aggregation.
    """
    raw_plans = fetch_raw_visit_plans_by_clinic()
    official_clinics = get_official_clinic_list()

    return f"""
    I need a Planned Visits Report grouped by Clinic.
    
    ### REFERENCE DATA (Clinic Registry with Location)
    {official_clinics}

    ### RAW DATA (Plan Counts by Clinic ID)
    {raw_plans}

    ### YOUR LOGIC REQUIREMENTS (Entity Resolution):
    You must decide which IDs represent the same real-world clinic and which are different.
    
    **Step 1: Analyze the Reference Data**
    - **CASE 1 & 2 (Merge Target):** If multiple IDs have the SAME (or fuzzy matched) Name AND similar Location (Address/City/Prov), treat them as ONE clinic.
      - *Example:* 'Klinik Permana' (ID 1) and 'Klinik Permana Sari' (ID 2) at the same address should be merged.
    - **CASE 3 (Split Target):** If multiple IDs have the SAME Name but COMPLETELY DIFFERENT Locations (City/Prov), treat them as DIFFERENT clinics.
      - *Example:* 'Clinic Kimia' in Jakarta vs 'Clinic Kimia' in Bali are different. Keep them separate.

    **Step 2: Aggregate Counts**
    - Look at the `RAW DATA`. Map every `ClinicID` to your resolved entities from Step 1.
    - If you merged IDs (e.g., ID 1 and ID 2), sum their visit counts together.

    ### OUTPUT FORMAT:
    Provide a Markdown table with these specific columns: 
    | Clinic ID(s) | Clinic Name | Number of Visits |
    | :--- | :--- | :--- |
    | 1, 5, 9 | Klinik Permana Sari (Merged) | 15 |
    | 2 | Clinic Kimia (Jakarta Branch) | 4 |
    | 3 | Clinic Kimia (Bali Branch) | 8 |
    """

@mcp.prompt()
def generate_planned_visits_report_by_customer() -> str:
    """
    Generates a smart report of planned visits that merges duplicate customer entries 
    using sophisticated Name Normalization and Phone verification.

    Injects:
    1. `customers://official_registry` (Resource) containing Name + Phone.
    2. `fetch_raw_visit_plans_by_customer` (Tool) containing raw counts by ID.

    Returns:
        str: A prompt instructing the AI to strip titles (drg, Sp.Ort) and merge NULL phones.
    """
    raw_plans = fetch_raw_visit_plans_by_customer()
    official_customers = get_official_customer_list()

    return f"""
    I need a Planned Visits Report grouped by Customer.
    
    ### REFERENCE DATA (Customer Registry with Phone)
    {official_customers}

    ### RAW DATA (Plan Counts by Customer ID)
    {raw_plans}

    ### CRITICAL FORMATTING RULE (PREVENT CSV BREAKAGE):
    - **IF** you generate any intermediate data, exports, or CSV text, **YOU MUST USE SEMICOLON (;)** as the delimiter.
    - **NEVER** use commas (,) as a delimiter, as this will split names like "Name, Sp.Ort".

    ### YOUR LOGIC REQUIREMENTS (Entity Resolution):
    You must decide which IDs represent the same real-world customer.
    
    **Step 1: Name Normalization (The "Core Name" Strategy)**
    Before comparing names, strip away all titles, degrees, and punctuation to find the "Core Name".
    - **Ignore/Remove these titles:** 'drg', 'dr', 'sp', 'ort', 'orto', 'mm', 'mkes', 'cert', 'fisid'.
    - **Ignore punctuation:** Remove periods (.), commas (,), and extra spaces.
    - *Example:* "drg. Jonathan Krisetya, Sp. Ort" -> Core Name: "jonathan krisetya"
    - *Example:* "Jonathan Krisetya" -> Core Name: "jonathan krisetya"
    - **Result:** These two entries now MATCH.

    **Step 2: Phone Number Verification (The "Wildcard" Rule)**
    Compare the Phone Numbers for entries with matching "Core Names":
    - **Match:** If Phone A == Phone B.
    - **Match (Wildcard):** If one phone is VALID (e.g., '0812...') and the other is NULL/Empty/'null', **TREAT AS A MATCH**. (Assume the entry with the phone number is the master record).
    - **No Match:** If Phone A != Phone B (and neither is null). Treat as different people (Case 3).

    **Step 3: Aggregate Counts**
    - Map every `CustID` from the `RAW DATA` to your resolved entities.
    - If you merged IDs (e.g. ID 315 and ID 679), sum their visit counts.
    - Use the **Most Complete Name** for the final display (the one with titles/degrees).

    ### OUTPUT FORMAT:
    Provide a Markdown table with these specific columns: 
    | Customer ID(s) | Customer Name | Number of Visits |
    | :--- | :--- | :--- |
    | 315; 679 | drg. Jonathan Krisetya, Sp. Ort (Merged) | 25 |
    | 502 | Budi Santoso | 8 |
    """

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="streamable-http")