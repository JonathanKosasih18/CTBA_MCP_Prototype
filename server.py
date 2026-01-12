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

def load_official_users_map():
    """
    Creates reference maps from the 'users' table.
    """
    id_map = {}     # ID -> User Object
    code_map = {}   # 'ps100' -> ID
    digit_map = {}  # '214' -> ID (Only if unique!)
    name_list = []  # List for fuzzy matching
    
    digit_counts = defaultdict(int)
    temp_digit_to_id = {}

    query = text("SELECT id, username, name FROM users")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            u_id = str(row.id)
            code = str(row.username).lower().strip() 
            name = row.name
            
            # Standard Maps
            id_map[u_id] = {"id": u_id, "code": row.username, "name": name}
            code_map[code] = u_id
            
            # Clean name for fuzzy list: "drg. Jonathan" -> "jonathan"
            clean_n = normalize_name(name) 
            name_list.append({"id": u_id, "name": clean_n})
            
            # Digit Map Logic
            digits = re.search(r'\d+', code)
            if digits:
                d_str = digits.group()
                digit_counts[d_str] += 1
                temp_digit_to_id[d_str] = u_id

    for d_str, count in digit_counts.items():
        if count == 1:
            digit_map[d_str] = temp_digit_to_id[d_str]
            
    return id_map, code_map, digit_map, name_list

def extract_salesman_code(text: str) -> str:
    """
    Attempts to find a code pattern (PS, DC, AM, etc.) in a messy string.
    Supported prefixes: PS, DC, AM, TS, CR, AC, SM, HR
    Example: 'AM 210 Wilson' -> 'am210'
    """
    if not text: return None
    
    # Updated Regex to include all new prefixes
    # \b ensures we match start of word
    # (ps|dc|...) captures the prefix
    # [\s\-\.]* allows flexible spacing (PS-100, PS 100, PS.100)
    # (\d+) captures the number
    pattern = r'\b(ps|dc|am|ts|cr|ac|sm|hr)[\s\-\.]*(\d+)\b'
    
    match = re.search(pattern, text.lower())
    if match:
        return f"{match.group(1)}{match.group(2)}" # returns ps100, am210, etc.
    return None

def clean_salesman_name(text: str) -> str:
    """
    Aggressively strips ALL distractions to find the 'Core Name'.
    Removes:
    1. Codes/Prefixes (PS, DC, AM...) even without numbers.
    2. Numbers (100, 214).
    3. Punctuation.
    
    Input: "Ps Gladys"       -> "gladys"
    Input: "214 Bryan"       -> "bryan"
    Input: "Mr. Ps. Gladys"  -> "gladys"
    """
    if not text: return ""
    text = text.lower()
    
    # 1. Strip known prefixes (word boundary \b ensures we don't kill 'AM' in 'AMANDA')
    # We look for these codes followed by space, dot, or end of string
    prefixes = r'\b(ps|dc|am|ts|cr|ac|sm|hr|mr|ms|mrs|dr)\b'
    text = re.sub(prefixes, ' ', text)
    
    # 2. Strip digits
    text = re.sub(r'\d+', ' ', text)
    
    # 3. Strip punctuation/symbols
    text = re.sub(r'[\W_]', ' ', text)
    
    # 4. Collapse whitespace
    return " ".join(text.split())

def resolve_salesman_identity(raw_text, code_map, digit_map, name_list):
    """
    Priority: Code -> Unique Digit -> Fuzzy Name
    """
    clean_text = raw_text.lower().strip()
    
    # 1. Strict Code Match (e.g. 'PS100')
    extracted_code = extract_salesman_code(clean_text)
    if extracted_code and extracted_code in code_map:
        return code_map[extracted_code]

    # 2. Loose Digit Match (e.g. '214')
    loose_digits = re.findall(r'\b\d+\b', clean_text)
    for d in loose_digits:
        if d in digit_map:
            return digit_map[d]

    # 3. Fuzzy Name Match
    # Use the AGGRESSIVE cleaner now
    core_name = clean_salesman_name(clean_text)
    
    if not core_name: return None

    official_names = [x['name'] for x in name_list]
    # Lower threshold slightly to catch short names like 'Yolan'
    match_name = get_fuzzy_match(core_name, official_names, threshold=0.80) 
    
    if match_name:
        for u in name_list:
            if u['name'] == match_name:
                return u['id']
                
    return None

def load_customer_directory():
    """
    Loads the 'Official' clean customer list from the 'customers' table.
    Now includes 'id' for the final report.
    Returns: [{'id': '101', 'name': 'Official Name', 'clean': 'normalized name'}]
    """
    targets = []
    # Added 'id' to the query
    query = text("SELECT id, custname FROM customers")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            if row.custname:
                targets.append({
                    "id": str(row.id),
                    "name": row.custname,
                    "clean": normalize_name(row.custname)
                })
    return targets

def load_acc_cid_map():
    """
    Loads mapping from Accounting IDs (cid) to Accounting Names.
    Returns: { 'CID123': 'Drg. Budi Santoso' }
    """
    mapping = {}
    query = text("SELECT cid, cust_name FROM acc_customers")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            if row.cid:
                mapping[str(row.cid).strip()] = row.cust_name
    return mapping

def normalize_product_name(text: str) -> str:
    """
    Normalizes product names for matching.
    CRITICAL: Keeps digits (022, 018) as they are often specs.
    Removes punctuation and extra whitespace.
    """
    if not text: return ""
    text = text.lower()
    
    # Replace punctuation (dots, dashes, brackets) with space
    # Keep A-Z, 0-9, and whitespace (\w includes digits)
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Collapse multiple spaces
    return " ".join(text.split())

def load_product_directory():
    """
    Loads the official product list from the 'products' table.
    Returns: 
    - id_map: { '101': 'Bracket System' } (ID -> Name)
    - name_list: List of clean names for fuzzy matching
    """
    id_map = {}
    name_list = []
    
    query = text("SELECT id, prodname FROM products")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            p_id = str(row.id)
            p_name = row.prodname
            
            id_map[p_id] = p_name
            # Store normalized version for fuzzy matching
            name_list.append({
                "id": p_id,
                "name": p_name,
                "clean": normalize_product_name(p_name)
            })
            
    return id_map, name_list

def normalize_clinic_name(text: str) -> str:
    """
    Normalizes clinic names by stripping facility types and punctuation.
    Input: "RS. Mitra Keluarga" -> "mitra keluarga"
    Input: "Klinik Gigi Sehat" -> "gigi sehat"
    """
    if not text: return ""
    text = text.lower()
    
    # 1. Strip standard facility prefixes (must be whole words)
    # rs = Rumah Sakit, rsia = RS Ibu & Anak, rsu = RS Umum, dr/drg = Doctor
    prefixes = r'\b(klinik|apotek|praktek|rs|rsia|rsu|dr|drg)\b'
    text = re.sub(prefixes, ' ', text)
    
    # 2. Strip punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # 3. Collapse whitespace
    return " ".join(text.split())

def load_clinic_directory():
    """
    Loads all clinics and groups them by CITY for safer fuzzy matching.
    
    CLEANING LOGIC:
    - If citycode is "Pilih Kota/Kab" or empty, it becomes '-'.
    - This ensures generic placeholders group together.
    
    Returns: 
        city_buckets: { 'JAKARTA': [ {id, name, clean, city_display}, ... ] }
    """
    city_buckets = defaultdict(list)
    
    # Fetch ID, Name, and City
    query = text("SELECT id, clinicname, citycode FROM clinics")
    
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            c_id = str(row.id)
            name = row.clinicname
            raw_city = str(row.citycode).strip() if row.citycode else ""
            
            # --- CLEAN CITY CODE ---
            # 1. Handle the specific placeholder "Pilih Kota/Kab" (case-insensitive check)
            if raw_city.lower() == "pilih kota/kab" or not raw_city:
                clean_city = "-"
            else:
                clean_city = raw_city
            
            # Use upper case for the bucket key to ensure case-insensitive grouping
            bucket_key = clean_city.upper()
            
            city_buckets[bucket_key].append({
                "id": c_id,
                "name": name,
                "clean": normalize_clinic_name(name),
                "city_display": clean_city # Store the specific display version
            })
            
    return city_buckets

# === MCP TOOLS (Dynamic Data Fetching) ===
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

@mcp.tool()
def fetch_deduplicated_sales_report() -> str:
    """
    Retrieves a consolidated Sales Performance Report.
    
    Columns: | Sales User ID | Sales Name | Transaction Count |
    """
    # 1. Load Source of Truth
    id_map, code_map, digit_map, name_list = load_official_users_map()
    
    query = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
    
    official_counts = defaultdict(int)
    unmatched_counts = defaultdict(int)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        
        for row in result:
            raw_field = str(row.salesman_name)
            count = row.c
            
            # Split logic
            parts = re.split(r'[/\&,]', raw_field)
            
            for part in parts:
                part = part.strip()
                if not part: continue
                
                # Attempt Resolution
                resolved_id = resolve_salesman_identity(part, code_map, digit_map, name_list)
                
                if resolved_id:
                    official_counts[resolved_id] += count
                else:
                    # Unmatched Grouping Logic
                    core_unmatched = clean_salesman_name(part)
                    if not core_unmatched:
                        core_unmatched = part.strip()
                    final_key = core_unmatched.title()
                    unmatched_counts[final_key] += count

    # Format Output
    output_rows = []
    
    # Official Matches
    for user_id, total in official_counts.items():
        user = id_map.get(user_id)
        if user:
            output_rows.append({
                "user_id": user['code'], # users.username
                "name": user['name'],    # users.name
                "count": total
            })
            
    # Unmatched Entries
    for name, total in unmatched_counts.items():
        output_rows.append({
            "user_id": "[NO CODE]", 
            "name": name, 
            "count": total
        })
    
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    md = "CONSOLIDATED SALES REPORT (Auto-Deduplicated):\n"
    md += "| Sales User ID | Sales Name | Transaction Count |\n"
    md += "| :--- | :--- | :--- |\n"
    
    for row in output_rows:
        md += f"| {row['user_id']} | {row['name']} | {row['count']} |\n"
        
    return md

@mcp.tool()
def fetch_transaction_report_by_customer_name() -> str:
    """
    Retrieves transaction counts grouped by CLEAN Customer Name with IDs.
    
    Now includes 'ID Normalization' to strip prefixes like 'B-' from 'B-CID00196'.
    """
    # 1. Load Reference Data
    official_customers = load_customer_directory()
    cid_to_name_map = load_acc_cid_map()
    
    # 2. Fetch Raw Transaction Counts
    query = text("""
        SELECT cust_id, COUNT(*) as c 
        FROM transactions 
        WHERE cust_id IS NOT NULL AND cust_id != ''
        GROUP BY cust_id
    """)
    
    grouped_data = defaultdict(lambda: {"count": 0, "id": "N/A"})
    
    with engine.connect() as conn:
        result = conn.execute(query)
        
        for row in result:
            raw_cid = str(row.cust_id).strip()
            count = row.c
            
            # --- STEP 0: ID NORMALIZATION (NEW) ---
            # Remove prefixes like 'B-' or 'A-' (Single uppercase letter followed by dash)
            # This turns 'B-CID00196' -> 'CID00196'
            clean_cid = re.sub(r'^[A-Z]-', '', raw_cid)
            
            # Use the CLEAN ID for all lookups
            t_cid = clean_cid
            
            # --- HOP 1: ID to Acc Name ---
            acc_name = cid_to_name_map.get(t_cid)
            
            if not acc_name:
                # If still unknown after cleaning, display the clean ID
                key = f"[Unknown ID] {t_cid}"
                grouped_data[key]["count"] += count
                grouped_data[key]["id"] = t_cid 
                continue
                
            # --- HOP 2: Acc Name to Clean Name ---
            clean_acc_name = normalize_name(acc_name)
            target_clean_names = [x['clean'] for x in official_customers]
            
            # Fuzzy Match
            match_clean = get_fuzzy_match(clean_acc_name, target_clean_names, threshold=0.85)
            
            if match_clean:
                # MATCH FOUND: Get Official Name AND Official ID
                official_entry = next((x for x in official_customers if x['clean'] == match_clean), None)
                if official_entry:
                    grouped_data[official_entry['name']]["count"] += count
                    grouped_data[official_entry['name']]["id"] = official_entry['id']
            else:
                # NO MATCH: Use formatted Acc Name
                # For the ID column, we prefer the 'CID' from transactions if available
                display_name = f"[New] {clean_acc_name.title()}" if clean_acc_name else acc_name
                
                grouped_data[display_name]["count"] += count
                grouped_data[display_name]["id"] = t_cid 

    # 3. Format Output
    output_rows = []
    for name, data in grouped_data.items():
        output_rows.append({
            "id": data["id"],
            "name": name,
            "count": data["count"]
        })
        
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    md = "CUSTOMER TRANSACTION REPORT (Linked & Deduplicated):\n"
    md += "| Customer ID | Customer Name | Transaction Count |\n"
    md += "| :--- | :--- | :--- |\n"
    
    for row in output_rows:
        md += f"| {row['id']} | {row['name']} | {row['count']} |\n"
        
    return md

@mcp.tool()
def fetch_visit_plans_by_salesman() -> str:
    """
    Retrieves the count of planned visits grouped by Salesman.
    
    Columns: | Sales User ID | Sales Name | Visit Count |
    """
    # 1. Load Source of Truth (Reuse existing map)
    id_map, code_map, digit_map, name_list = load_official_users_map()
    
    # 2. Fetch Raw Plan Counts (Grouped by User ID)
    query = text("SELECT userid, COUNT(*) as c FROM plans GROUP BY userid")
    
    output_rows = []
    
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            u_id = str(row.userid)
            count = row.c
            
            # 3. Lookup User Details
            user = id_map.get(u_id)
            
            if user:
                # MATCH FOUND
                output_rows.append({
                    "user_id": user['code'], # users.username (e.g. PS101)
                    "name": user['name'],    # users.name
                    "count": count
                })
            else:
                # NO MATCH (Integrity Error in DB?)
                output_rows.append({
                    "user_id": f"ID {u_id}",
                    "name": "[Unknown User]",
                    "count": count
                })
                
    # 4. Sort and Format
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    md = "PLANNED VISITS REPORT (Grouped by Salesman):\n"
    md += "| Sales User ID | Salesman Name | Visit Count |\n"
    md += "| :--- | :--- | :--- |\n"
    
    for row in output_rows:
        md += f"| {row['user_id']} | {row['name']} | {row['count']} |\n"
        
    return md

@mcp.tool()
def fetch_transaction_report_by_product() -> str:
    """
    Retrieves sales performance grouped by Product.
    
    CORRECTED METRICS:
    - Units Sold: Sum of 'qty' column (not count of rows).
    - Total Revenue: Sum of 'amount' column.
    
    LOGIC:
    1. Exact ID Match.
    2. Containment Match (e.g., 'Angel Aligner' inside 'Angel Aligner Select').
    3. Fuzzy Match.
    """
    # 1. Load Reference Data
    id_to_name, official_products = load_product_directory()
    
    # Sort by length for containment logic (Longest first)
    official_products.sort(key=lambda x: len(x['clean']), reverse=True)
    target_clean_names = [x['clean'] for x in official_products]
    
    # 2. Fetch Raw Data (Now summing QTY and AMOUNT)
    query = text("""
        SELECT item_id, product, SUM(qty) as units, SUM(amount) as revenue 
        FROM transactions 
        GROUP BY item_id, product
    """)
    
    grouped_data = defaultdict(lambda: {"count": 0, "revenue": 0})
    
    with engine.connect() as conn:
        result = conn.execute(query)
        
        for row in result:
            raw_id = str(row.item_id).strip() if row.item_id else ""
            raw_name = str(row.product)
            
            # CRITICAL FIX: Use SUM(qty) instead of row count
            units = int(row.units) if row.units else 0
            revenue = int(row.revenue) if row.revenue else 0
            
            clean_raw = normalize_product_name(raw_name)
            match_found = False
            
            # --- STRATEGY 1: Exact ID Match ---
            if raw_id and raw_id in id_to_name:
                official_name = id_to_name[raw_id]
                grouped_data[official_name]["count"] += units
                grouped_data[official_name]["revenue"] += revenue
                match_found = True
                
            # --- STRATEGY 2: Containment Match ---
            if not match_found and clean_raw:
                for official in official_products:
                    # Check if Official Name is inside Raw Name (e.g. "Angel Aligner" in "Angel Aligner Select")
                    if f" {official['clean']} " in f" {clean_raw} ":
                        grouped_data[official['name']]["count"] += units
                        grouped_data[official['name']]["revenue"] += revenue
                        match_found = True
                        break 
            
            # --- STRATEGY 3: Fuzzy Match ---
            if not match_found and clean_raw:
                match_clean = get_fuzzy_match(clean_raw, target_clean_names, threshold=0.70)
                if match_clean:
                    official_entry = next((x for x in official_products if x['clean'] == match_clean), None)
                    if official_entry:
                        grouped_data[official_entry['name']]["count"] += units
                        grouped_data[official_entry['name']]["revenue"] += revenue
                        match_found = True
            
            # --- FALLBACK ---
            if not match_found:
                clean_display = clean_raw.title() if clean_raw else "[Unknown Product]"
                display_name = f"[Uncategorized] {clean_display}"
                grouped_data[display_name]["count"] += units
                grouped_data[display_name]["revenue"] += revenue

    # 3. Format Output
    output_rows = []
    for name, data in grouped_data.items():
        output_rows.append({
            "name": name,
            "count": data["count"],
            "revenue": data["revenue"]
        })
        
    output_rows.sort(key=lambda x: x['revenue'], reverse=True)
    
    md = "PRODUCT SALES REPORT (Consolidated):\n"
    md += "| Product Name | Units Sold (Qty) | Total Revenue |\n"
    md += "| :--- | :--- | :--- |\n"
    
    for row in output_rows:
        rev_formatted = f"{row['revenue']:,}"
        md += f"| {row['name']} | {row['count']} | {rev_formatted} |\n"
        
    return md

@mcp.tool()
def fetch_visit_plans_by_clinic() -> str:
    """
    Retrieves planned visits grouped by Clinic Name.
    
    Columns: | Clinic ID(s) | Clinic Name | Clinic Address (City) | Number of Visits |
    """
    # 1. Load Reference Data (Grouped by City)
    city_buckets = load_clinic_directory()
    
    # 2. Fetch Raw Plan Counts
    query = text("SELECT cliniccode, COUNT(*) as c FROM plans GROUP BY cliniccode")
    visit_counts = defaultdict(int)
    
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            visit_counts[str(row.cliniccode)] = row.c
            
    # 3. Entity Resolution (City-by-City)
    final_output = []
    
    for bucket_key, clinics in city_buckets.items():
        # Group duplicates within this specific city bucket
        grouped_map = defaultdict(list)
        
        # Sort longest to shortest for better matching
        clinics.sort(key=lambda x: len(x['clean']), reverse=True)
        
        for clinic in clinics:
            core_name = clinic['clean']
            if not core_name: continue 
            
            # Fuzzy match against keys IN THIS CITY only
            potential_matches = list(grouped_map.keys())
            match = get_fuzzy_match(core_name, potential_matches, threshold=0.88)
            
            if match:
                grouped_map[match].append(clinic)
            else:
                grouped_map[core_name].append(clinic)
        
        # 4. Aggregate Counts
        for clean_key, entries in grouped_map.items():
            ids = [x['id'] for x in entries]
            total_visits = sum(visit_counts.get(cid, 0) for cid in ids)
            
            if total_visits > 0:
                # Pick best display name
                display_name = max((x['name'] for x in entries), key=len)
                
                # Pick the city code for display (they are all the same in this bucket)
                # We use the 'city_display' from the first entry
                display_city = entries[0]['city_display']
                
                final_output.append({
                    "ids": ", ".join(ids),
                    "name": display_name,
                    "city": display_city,
                    "count": total_visits
                })

    # 5. Sort & Format
    final_output.sort(key=lambda x: x['count'], reverse=True)
    
    md = "PLANNED VISITS REPORT (Grouped by Clinic):\n"
    md += "| Clinic ID(s) | Clinic Name | Clinic Address | Number of Visits |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    
    for row in final_output:
        md += f"| {row['ids']} | {row['name']} | {row['city']} | {row['count']} |\n"
        
    return md

@mcp.tool()
def fetch_report_counts_by_salesman() -> str:
    """
    Retrieves the count of completed reports grouped by Salesman.
    
    Logic:
    1. JOINS 'reports' to 'plans' (on reports.idplan = plans.id).
    2. Groups by 'plans.userid'.
    3. Maps User ID to Official Name.
    
    Columns: | Sales User ID | Salesman Name | Total Reports |
    """
    # 1. Load Source of Truth
    id_map, code_map, digit_map, name_list = load_official_users_map()
    
    # 2. Fetch Report Counts via Join
    # We join reports -> plans to get the userid associated with the report
    query = text("""
        SELECT p.userid, COUNT(r.id) as c 
        FROM reports r
        JOIN plans p ON r.idplan = p.id
        GROUP BY p.userid
    """)
    
    output_rows = []
    
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            u_id = str(row.userid)
            count = row.c
            
            # 3. Lookup User Details
            user = id_map.get(u_id)
            
            if user:
                output_rows.append({
                    "user_id": user['code'], 
                    "name": user['name'],    
                    "count": count
                })
            else:
                output_rows.append({
                    "user_id": f"ID {u_id}",
                    "name": "[Unknown User]",
                    "count": count
                })
                
    # 4. Sort and Format
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    md = "COMPLETED REPORTS BY SALESMAN:\n"
    md += "| Sales User ID | Salesman Name | Total Reports |\n"
    md += "| :--- | :--- | :--- |\n"
    
    for row in output_rows:
        md += f"| {row['user_id']} | {row['name']} | {row['count']} |\n"
        
    return md

@mcp.tool()
def fetch_comprehensive_salesman_performance() -> str:
    """
    Retrieves a 360-degree performance report for Salesmen.
    Aggregates Plans, Reports (Visits), and Transactions into a single view.
    
    Metrics:
    - Plans: From 'plans' table.
    - Visits: From 'reports' table (linked to plans).
    - Transactions: From 'transactions' table (deduplicated & resolved).
    - Ratios: Calculated fields (Visits/Plans and Transactions/Visits).
    """
    # 1. Load Source of Truth
    id_map, code_map, digit_map, name_list = load_official_users_map()

    # Master Data Structure: { user_id: { plans: 0, reports: 0, transactions: 0 } }
    master_data = defaultdict(lambda: {'plans': 0, 'reports': 0, 'transactions': 0})

    # --- METRIC 1: PLANS ---
    # Source: plans table (Linked directly to users)
    with engine.connect() as conn:
        q_plans = text("SELECT userid, COUNT(*) as c FROM plans GROUP BY userid")
        for row in conn.execute(q_plans):
            uid = str(row.userid)
            if uid in id_map:
                master_data[uid]['plans'] += row.c

    # --- METRIC 2: REPORTS (VISITS) ---
    # Source: reports table (Linked to plans -> users)
    with engine.connect() as conn:
        q_reports = text("""
            SELECT p.userid, COUNT(r.id) as c 
            FROM reports r
            JOIN plans p ON r.idplan = p.id
            GROUP BY p.userid
        """)
        for row in conn.execute(q_reports):
            uid = str(row.userid)
            if uid in id_map:
                master_data[uid]['reports'] += row.c

    # --- METRIC 3: TRANSACTIONS ---
    # Source: transactions table (Messy names -> Python Resolution -> User ID)
    with engine.connect() as conn:
        q_trans = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
        for row in conn.execute(q_trans):
            raw_field = str(row.salesman_name)
            count = row.c
            
            # Reuse logic from deduplicated sales report
            parts = re.split(r'[/\&,]', raw_field)
            for part in parts:
                part = part.strip()
                if not part: continue
                
                # Resolve Identity
                resolved_id = resolve_salesman_identity(part, code_map, digit_map, name_list)
                
                if resolved_id:
                    master_data[resolved_id]['transactions'] += count
                # Note: Unmatched transactions ([NO CODE]) are excluded from this specific 
                # report because they don't have a User ID/Username to fit the columns.

    # --- FORMAT OUTPUT ---
    output_rows = []
    
    for uid, stats in master_data.items():
        user = id_map.get(uid)
        if not user: continue
        
        plans = stats['plans']
        reports = stats['reports']
        trans = stats['transactions']
        
        # Calculate Ratios (Safety check for division by zero)
        
        # 1. Plan to Visit Ratio (Completion Rate): Reports / Plans
        if plans > 0:
            ratio_pv = reports / plans
        else:
            ratio_pv = 0.0
            
        # 2. Visit to Transaction Ratio (Conversion Rate): Transactions / Reports
        if reports > 0:
            ratio_vt = trans / reports
        else:
            # If transactions exist but 0 visits (phone orders?), ratio is just the raw count or handle as exception
            ratio_vt = float(trans) if trans > 0 else 0.0
        
        output_rows.append({
            "code": user['code'],
            "name": user['name'],
            "plans": plans,
            "reports": reports,
            "transactions": trans,
            "ratio_pv": ratio_pv,
            "ratio_vt": ratio_vt
        })

    # Sort by Total Transactions Descending
    output_rows.sort(key=lambda x: x['transactions'], reverse=True)

    # Markdown Construction
    md = "SALESMAN PERFORMANCE SCORECARD (360 View):\n"
    md += "| Sales User ID | Salesman Name | Total Plans | Total Visits | Total Transactions | Plan to Visit Ratio | Visit to Transaction Ratio |\n"
    md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    
    for row in output_rows:
        pv_str = f"{row['ratio_pv']:.2f}"
        vt_str = f"{row['ratio_vt']:.2f}"
        
        md += f"| {row['code']} | {row['name']} | {row['plans']} | {row['reports']} | {row['transactions']} | {pv_str} | {vt_str} |\n"
        
    return md

# === MCP PROMPTS (Agent Instructions) ===
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

@mcp.prompt()
def generate_planned_visits_report_by_salesman() -> str:
    """
    Generates a prompt to request the planned visits report grouped by salesman.
    """
    return """
    I need a Planned Visits Report grouped by Salesman.
    
    Please run the tool `fetch_visit_plans_by_salesman`.
    
    Output the table exactly as returned by the tool.
    """

@mcp.prompt()
def generate_planned_visits_report_by_clinic() -> str:
    """
    Generates a prompt to request the planned visits report grouped by clinic.
    """
    return """
    I need a Planned Visits Report grouped by Clinic.
    
    Please run the tool `fetch_visit_plans_by_clinic`.
    
    This tool automatically:
    1. Distinguishes branches by City Code (replacing 'Pilih Kota/Kab' with '-').
    2. Merges duplicate entries within the same city.
    3. Aggregates the visit counts.
    
    The output will be a table with columns: 
    | Clinic ID(s) | Clinic Name | Clinic Address | Number of Visits |
    """

@mcp.prompt()
def generate_transaction_report_by_salesmen() -> str:
    """
    Generates a prompt to request the consolidated sales report.
    Uses `fetch_deduplicated_sales_report` to do the heavy lifting.
    """
    return """
    I need the Sales Performance Report.
    
    Please run the tool `fetch_deduplicated_sales_report`.
    
    This tool will automatically:
    1. Split multi-salesman entries (giving full credit to each).
    2. Normalize names based on the User Database.
    3. Aggregate the data.
    
    Display the returned table exactly as is.
    """

@mcp.prompt()
def generate_transaction_report_by_customer() -> str:
    """
    Generates a prompt to request the customer transaction report.
    """
    return """
    I need the Transaction Report grouped by Customer Name.
    
    Please run the tool `fetch_transaction_report_by_customer_name`.
    
    This tool automatically:
    1. Links Transaction IDs to Accounting Names.
    2. Fuzzy matches Accounting Names to the Official Customer Database.
    3. Aggregates the data.
    """

@mcp.prompt()
def generate_transaction_report_by_product() -> str:
    """
    Generates a prompt to request the product sales report.
    """
    return """
    I need the Transaction Report grouped by Product.
    
    Please run the tool `fetch_transaction_report_by_product`.
    
    This tool automatically:
    1. Normalizes messy product names based on the Product List.
    2. Links Transaction IDs to the Official Product List.
    3. Aggregates Units Sold and Revenue.
    """

@mcp.prompt()
def generate_report_counts_by_salesman() -> str:
    """
    Generates a prompt to request the count of completed visit reports grouped by salesman.
    """
    return """
    I need a Report on Completed Visits (Reports) grouped by Salesman.
    
    Please run the tool `fetch_report_counts_by_salesman`.
    
    This tool automatically:
    1. Links Reports -> Plans -> Users.
    2. Aggregates the count of reports per salesman.
    
    Output the table exactly as returned by the tool.
    """

@mcp.prompt()
def generate_comprehensive_salesman_report() -> str:
    """
    Generates a prompt for the all-in-one Salesman Performance Scorecard.
    """
    return """
    I need the Comprehensive Salesman Performance Report (Scorecard).
    
    Please run the tool `fetch_comprehensive_salesman_performance`.
    
    This tool combines data from Plans, Reports, and Transactions into one table with:
    1. Identity Resolution (mapping messy transaction names to official users).
    2. Aggregated counts for Plans, Visits, and Sales.
    3. Performance Ratios (Plan Completion & Conversion Rate).
    
    Display the result exactly as returned.
    """

# Run the MCP server
if __name__ == "__main__":
    mcp.run(transport="sse")