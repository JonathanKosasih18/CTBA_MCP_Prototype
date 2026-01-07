import difflib
import os
import re
from dotenv import load_dotenv
from collections import defaultdict
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

# PYTHON HELPER FUNCTIONS

def normalize_name(text: str) -> str:
    """
    Strips titles, degrees, and punctuation to find the 'Core Name'.
    Handles complex variations like 'M.Kes', 'Cert. Ort', and 'Sp. Ort'.
    """
    if not text: return ""
    
    # Lowercase for consistency
    core = text.lower()
    
    # --- PHASE A: Remove Complex/Compound Titles (Order Matters) ---
    # We use Regex to catch "spaced" titles before removing punctuation
    
    # 1. Handle "Sp. Ort" / "Sp Ort" / "Sp.Orto"
    core = re.sub(r'\bsp[\s\.]*ort[a-z]*\b', '', core)
    
    # 2. Handle "M.Kes" / "M Kes" / "M. Kes"
    core = re.sub(r'\bm[\s\.]*kes\b', '', core)
    
    # 3. Handle "Cert. Ort" / "Cert Ort"
    core = re.sub(r'\bcert[\s\.]*ort[a-z]*\b', '', core)
    
    # --- PHASE B: Remove Punctuation ---
    # Replace dots, commas, dashes with spaces so "drg.name" becomes "drg name"
    core = re.sub(r'[.,\-]', ' ', core)
    
    # --- PHASE C: Remove Standalone Titles ---
    # List of titles to strip (must be whole words)
    titles = {
        'drg', 'dr', 'drs', 'dra', 
        'sp', 'spd', 'ort', 'orto', 'mm', 'mkes', 
        'cert', 'fisid', 'kg', 'mha', 'sph', 'amd', 'skg'
    }
    
    tokens = core.split()
    clean_tokens = [t for t in tokens if t not in titles]
    
    return " ".join(clean_tokens)

def normalize_phone(phone: str) -> str:
    if not phone or str(phone).lower() in ['null', 'none', 'nan']:
        return None
    
    # Remove non-digits
    clean_num = re.sub(r'\D', '', str(phone))
    
    # Handle Country Code (+62 -> 0)
    if clean_num.startswith('62'):
        clean_num = '0' + clean_num[2:]
        
    return clean_num

def get_fuzzy_match(name, existing_names, threshold=0.9):
    """
    Checks if 'name' is similar to any key in 'existing_names' (Case 3 Fix).
    Uses difflib.SequenceMatcher.
    """
    # Quick optimization: check simple containment or very high similarity
    matches = difflib.get_close_matches(name, existing_names, n=1, cutoff=threshold)
    return matches[0] if matches else None

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
'''
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
'''

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
def fetch_deduplicated_visit_report() -> str:
    """
    Retrieves a consolidated report of planned visits.
    
    This tool performs internal "Entity Resolution":
    1. Fetches raw visit counts.
    2. Fetches customer details (Name + Phone).
    3. Merges customers based on Fuzzy Name Matching AND Phone number matching.
    4. Aggregates the visit counts.
    """
    # 1. Fetch Visit Counts
    visit_counts = defaultdict(int)
    query_plans = text("SELECT custcode, COUNT(*) as c FROM plans GROUP BY custcode")
    
    with engine.connect() as conn:
        result = conn.execute(query_plans)
        for row in result:
            visit_counts[str(row.custcode)] = row.c

    # 2. Fetch Customer Details
    customers = []
    query_cust = text("SELECT id, custname, phone FROM customers")
    
    with engine.connect() as conn:
        result = conn.execute(query_cust)
        for row in result:
            customers.append({
                "id": str(row.id),
                "name": row.custname,
                "phone": row.phone
            })

    # 3. ROBUST GROUPING (Regex + Fuzzy Match)
    grouped_map = defaultdict(list)
    
    for cust in customers:
        core_name = normalize_name(cust['name'])
        
        # --- FUZZY MATCH LOGIC ---
        if not core_name:
            continue

        # Optimization: Only compare with keys starting with the same letter
        potential_matches = [k for k in grouped_map.keys() if k and k[0] == core_name[0]]
        
        # Check if we already have a key similar to this core_name
        match = get_fuzzy_match(core_name, potential_matches, threshold=0.92)
        
        if match:
            # If match found, use the existing key (merging them)
            grouped_map[match].append(cust)
        else:
            # If no match, create a new entry
            grouped_map[core_name].append(cust)

    # 4. PHONE WILDCARD MERGE & AGGREGATION
    final_rows = []

    for core_name, entries in grouped_map.items():
        # ### EDITED: Removed all phone bucket logic.
        # Previously we split 'entries' into 'phone_buckets'.
        # Now we treat ALL 'entries' in this group as the same person.
        
        # Collect all IDs in this group
        ids = [x['id'] for x in entries]
        
        # Sum the visit counts for ALL these IDs
        total_visits = sum(visit_counts.get(cust_id, 0) for cust_id in ids)
        
        # Pick the longest name as the "Display Name" (usually contains titles)
        display_name = max((x['name'] for x in entries), key=len)
        
        # Only add to report if visits exist (optional, removes clutter)
        if total_visits > 0:
            final_rows.append({
                "ids": "; ".join(ids),
                "name": display_name,
                "count": total_visits
            })

    # Sort by visit count descending
    final_rows.sort(key=lambda x: x['count'], reverse=True)

    output = "CONSOLIDATED VISIT REPORT (Auto-Deduplicated):\n"
    output += "| Customer ID(s) | Customer Name | Number of Visits |\n"
    output += "| :--- | :--- | :--- |\n"
    
    for row in final_rows:
        output += f"| {row['ids']} | {row['name']} | {row['count']} |\n"
        
    return output

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
    Generates a prompt that instructs the LLM to retrieve a pre-calculated, deduplicated visit report.
    This prompt relies on the `fetch_deduplicated_visit_report` tool for all logic.
    """
    return """
    I need a Planned Visits Report grouped by Customer.
    
    Please run the tool `fetch_deduplicated_visit_report`.
    
    This tool has built-in logic to:
    1. Clean and normalize messy names (stripping titles like 'drg', 'Sp.Ort').
    2. Merge duplicate customer entries based on Fuzzy Name Matching (typo tolerance).
    3. Aggregate the visit counts for these merged identities automatically.
    
    Output the result exactly as the tool returns it (Markdown Table).
    """

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="sse")