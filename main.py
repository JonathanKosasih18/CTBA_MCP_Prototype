import os
import re
import difflib
import datetime
import pytz
import json
import uvicorn
import contextlib
from typing import Any, Optional, Union, List, Dict
from collections import defaultdict
from dotenv import load_dotenv

# SQLAlchemy Imports
from sqlalchemy import create_engine, text

# FastAPI Imports
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

# MCP Imports
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# ==========================================
# 1. CONFIGURATION & DATABASE
# ==========================================

# Load environment variables
load_dotenv()

# MySQL Database Connection
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

# ==========================================
# 2. MCP SERVER INSTANCE
# ==========================================

mcp = FastMCP(
    "CTBA MCP",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
        allowed_hosts=["*"] 
    )
)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================

def normalize_name(text: str) -> str:
    if not text: return ""
    core = text.lower()
    core = re.sub(r'\bsp[\s\.]*ort[a-z]*\b', '', core)
    core = re.sub(r'\bm[\s\.]*kes\b', '', core)
    core = re.sub(r'\bcert[\s\.]*ort[a-z]*\b', '', core)
    core = re.sub(r'[.,\-]', ' ', core)
    titles = {
        'drg', 'dr', 'drs', 'dra', 'sp', 'spd', 'ort', 'orto', 'mm', 'mkes', 
        'cert', 'fisid', 'kg', 'mha', 'sph', 'amd', 'skg'
    }
    tokens = core.split()
    clean_tokens = [t for t in tokens if t not in titles]
    return " ".join(clean_tokens)

def normalize_phone(phone: str) -> str:
    if not phone or str(phone).lower() in ['null', 'none', 'nan']:
        return None
    clean_num = re.sub(r'\D', '', str(phone))
    if clean_num.startswith('62'):
        clean_num = '0' + clean_num[2:]
    return clean_num

def normalize_product_name(text: str) -> str:
    if not text: return ""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return " ".join(text.split())

def normalize_clinic_name(text: str) -> str:
    if not text: return ""
    text = text.lower()
    prefixes = r'\b(klinik|apotek|praktek|rs|rsia|rsu|dr|drg)\b'
    text = re.sub(prefixes, ' ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    return " ".join(text.split())

def extract_salesman_code(text: str) -> str:
    if not text: return None
    pattern = r'\b(ps|dc|am|ts|cr|ac|sm|hr)[\s\-\.]*(\d+)\b'
    match = re.search(pattern, text.lower())
    if match:
        return f"{match.group(1)}{match.group(2)}"
    return None

def clean_salesman_name(text: str) -> str:
    if not text: return ""
    text = text.lower()
    prefixes = r'\b(ps|dc|am|ts|cr|ac|sm|hr|mr|ms|mrs|dr)\b'
    text = re.sub(prefixes, ' ', text)
    text = re.sub(r'\d+', ' ', text)
    text = re.sub(r'[\W_]', ' ', text)
    return " ".join(text.split())

def get_fuzzy_match(name, existing_names, threshold=0.9):
    matches = difflib.get_close_matches(name, existing_names, n=1, cutoff=threshold)
    return matches[0] if matches else None

def resolve_salesman_identity(raw_text, code_map, digit_map, name_list):
    clean_text = raw_text.lower().strip()
    extracted_code = extract_salesman_code(clean_text)
    if extracted_code and extracted_code in code_map:
        return code_map[extracted_code]
    loose_digits = re.findall(r'\b\d+\b', clean_text)
    for d in loose_digits:
        if d in digit_map:
            return digit_map[d]
    core_name = clean_salesman_name(clean_text)
    if not core_name: return None
    official_names = [x['name'] for x in name_list]
    match_name = get_fuzzy_match(core_name, official_names, threshold=0.80) 
    if match_name:
        for u in name_list:
            if u['name'] == match_name:
                return u['id']
    return None

def standardize_customer_id(text: str) -> str:
    """
    Standardizes Customer ID to 'CIDxxxxx' format.
    Removes 'B-' prefixes and ensures numeric part is prefixed with CID.
    """
    if not text or str(text).lower() in ['none', 'nan', '']:
        return "N/A"
    
    clean = str(text).upper().strip()
    
    # Specific fix for "B-CID..." format mentioned
    clean = re.sub(r'^B[-_]*', '', clean)
    
    # Extract digits. If digits exist, format as CID{digits}
    # This preserves leading zeros (e.g. 00196) if they exist in the text
    digits = re.search(r'\d+', clean)
    if digits:
        return f"CID{digits.group()}"
    
    return clean

def load_name_to_cid_map():
    """
    Loads a mapping of Normalized Name -> CID from acc_customers.
    Used to bridge the gap between Plans (linked to internal ID) and CID.
    """
    name_to_cid = {}
    query = text("SELECT cid, cust_name FROM acc_customers")
    with engine.connect() as conn:
        for row in conn.execute(query):
            if row.cid and row.cust_name:
                clean_name = normalize_name(row.cust_name)
                if clean_name:
                    std_cid = standardize_customer_id(row.cid)
                    name_to_cid[clean_name] = std_cid
    return name_to_cid

# --- DATABASE LOADERS ---

def load_official_users_map():
    id_map, code_map, digit_map, name_list = {}, {}, {}, []
    digit_counts = defaultdict(int)
    temp_digit_to_id = {}
    
    query = text("SELECT id, username, name, level FROM users")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            u_id = str(row.id)
            code = str(row.username).lower().strip() 
            name = row.name
            
            raw_level = row.level
            if not raw_level or str(raw_level).lower() in ['null', 'none', '']:
                level = "NULL"
            else:
                level = str(raw_level).upper().strip()

            id_map[u_id] = {"id": u_id, "code": row.username, "name": name, "level": level}
            
            code_map[code] = u_id
            clean_n = normalize_name(name) 
            name_list.append({"id": u_id, "name": clean_n})
            
            digits = re.search(r'\d+', code)
            if digits:
                d_str = digits.group()
                digit_counts[d_str] += 1
                temp_digit_to_id[d_str] = u_id
                
    for d_str, count in digit_counts.items():
        if count == 1:
            digit_map[d_str] = temp_digit_to_id[d_str]
            
    return id_map, code_map, digit_map, name_list

def load_customer_directory():
    targets = []
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
    mapping = {}
    query = text("SELECT cid, cust_name FROM acc_customers")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            if row.cid:
                mapping[str(row.cid).strip()] = row.cust_name
    return mapping

def load_product_directory():
    id_map, name_list = {}, []
    query = text("SELECT id, prodname FROM products")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            p_id = str(row.id)
            p_name = row.prodname
            id_map[p_id] = p_name
            name_list.append({
                "id": p_id,
                "name": p_name,
                "clean": normalize_product_name(p_name)
            })
    return id_map, name_list

def load_clinic_directory():
    city_buckets = defaultdict(list)
    query = text("SELECT id, clinicname, citycode FROM clinics")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            c_id = str(row.id)
            name = row.clinicname
            raw_city = str(row.citycode).strip() if row.citycode else ""
            if raw_city.lower() == "pilih kota/kab" or not raw_city:
                clean_city = "-"
            else:
                clean_city = raw_city
            bucket_key = clean_city.upper()
            city_buckets[bucket_key].append({
                "id": c_id,
                "name": name,
                "clean": normalize_clinic_name(name),
                "city_display": clean_city
            })
    return city_buckets

def get_default_dates(start_date: Optional[str], end_date: Optional[str]):
    """
    Handles default date logic for transaction filters.
    Default Start: 2015-01-01
    Default End: Current Date (Asia/Jakarta)
    """
    tz = pytz.timezone('Asia/Jakarta')
    today = datetime.datetime.now(tz).strftime('%Y-%m-%d')
    
    final_start = start_date if start_date and start_date.strip() else '2015-01-01'
    final_end = end_date if end_date and end_date.strip() else today
    
    return final_start, final_end

# --- ANALYTICAL HELPERS ---

def find_salesman_id_by_name(name_query: str):
    """
    Searches for a salesman's Official ID based on a name string.
    Returns: (id, name) or (None, None)
    """
    id_map, code_map, digit_map, name_list = load_official_users_map()
    resolved_id = resolve_salesman_identity(name_query, code_map, digit_map, name_list)
    if resolved_id:
        return resolved_id, id_map[resolved_id]['name']
    return None, None

def fetch_single_salesman_data(salesman_name: str) -> Dict[str, Any]:
    """
    Retrieves transaction count and visit notes for a single salesman.
    Returns a Dictionary object.
    """
    # 1. Identify Salesman
    target_id, official_name = find_salesman_id_by_name(salesman_name)
    
    if not target_id:
        return {"error": f"Could not find salesman '{salesman_name}'."}
    
    # 2. Get Transaction Count
    id_map, code_map, digit_map, name_list = load_official_users_map()
    transaction_count = 0
    
    query_trans = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
    with engine.connect() as conn:
        for row in conn.execute(query_trans):
            parts = re.split(r'[/\&,]', str(row.salesman_name))
            for part in parts:
                part = part.strip()
                if not part: continue
                resolved = resolve_salesman_identity(part, code_map, digit_map, name_list)
                if resolved == target_id:
                    transaction_count += row.c

    # 3. Count Total Visits (use COUNT on reports, not len of notes)
    visit_notes = []
    visit_count_query = text("""
        SELECT COUNT(r.id) as c
        FROM reports r
        JOIN plans p ON r.idplan = p.id
        WHERE p.userid = :uid
    """)
    with engine.connect() as conn:
        row = conn.execute(visit_count_query, {"uid": target_id}).fetchone()
        total_visits = int(row.c) if row and row.c else 0

    # 4. Get Recent Visit Notes (limited to 50)
    query_notes = text("""
        SELECT r.visitnote 
        FROM reports r
        JOIN plans p ON r.idplan = p.id
        WHERE p.userid = :uid
        ORDER BY r.date DESC
        LIMIT 30
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query_notes, {"uid": target_id})
        for row in result:
            if row.visitnote and str(row.visitnote).strip():
                visit_notes.append(str(row.visitnote).strip())

    # --- RETURN DICTIONARY ---
    return {
        "id": target_id,
        "name": official_name,
        "total_transactions": transaction_count,
        "total_visits": total_visits,
        "recent_notes": visit_notes
    }

def fetch_best_performers_logic(start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Determines best performers with rigorous Identity Resolution for Salesmen
    and Fuzzy Matching for Products.
    Returns a Dictionary object.
    """

    # --- 1. PRE-LOAD REFERENCE MAPS ---
    id_map, code_map, digit_map, name_list = load_official_users_map()
    prod_id_map, official_products = load_product_directory()
    official_products.sort(key=lambda x: len(x['clean']), reverse=True)
    target_product_cleans = [x['clean'] for x in official_products]

    # Stats Container
    stats = defaultdict(lambda: {"name": "Unknown", "visits": 0, "trans": 0, "rev": 0})
    product_stats = defaultdict(int)

    with engine.connect() as conn:
        # --- 2. PROCESS VISITS ---
        visit_query = text("""
            SELECT p.userid, u.name, COUNT(r.id) as visit_count
            FROM reports r
            JOIN plans p ON r.idplan = p.id
            JOIN users u ON p.userid = u.id
            WHERE r.date BETWEEN :start AND :end
            GROUP BY p.userid, u.name
        """)
        
        result_visits = conn.execute(visit_query, {"start": start_date, "end": end_date})
        for row in result_visits:
            u_id = str(row.userid)
            stats[u_id]["visits"] = row.visit_count
            stats[u_id]["name"] = row.name 

        # --- 3. PROCESS TRANSACTIONS ---
        trans_query = text("""
            SELECT salesman_name, product, qty, amount 
            FROM transactions
            WHERE inv_date BETWEEN :start AND :end
        """)
        
        result_trans = conn.execute(trans_query, {"start": start_date, "end": end_date})
        
        for row in result_trans:
            raw_salesman = str(row.salesman_name) if row.salesman_name else ""
            raw_product = str(row.product) if row.product else ""
            qty = int(row.qty) if row.qty else 0
            revenue = int(row.amount) * qty if row.amount else 0

            # --- A. RESOLVE SALESMAN ---
            resolved_id = resolve_salesman_identity(raw_salesman, code_map, digit_map, name_list)
            target_key = None
            if resolved_id:
                target_key = resolved_id
                if stats[target_key]["name"] == "Unknown":
                    stats[target_key]["name"] = id_map[resolved_id]['name']
            else:
                clean_n = clean_salesman_name(raw_salesman).title()
                if clean_n:
                    target_key = clean_n
                    if stats[target_key]["name"] == "Unknown":
                        stats[target_key]["name"] = clean_n

            if target_key:
                stats[target_key]["trans"] += 1 
                stats[target_key]["rev"] += revenue

            # --- B. RESOLVE PRODUCT ---
            clean_prod = normalize_product_name(raw_product)
            match_found = False
            
            if clean_prod:
                for official in official_products:
                    if f" {official['clean']} " in f" {clean_prod} ":
                        product_stats[official['name']] += qty
                        match_found = True
                        break
                if not match_found:
                    fuzzy_match = get_fuzzy_match(clean_prod, target_product_cleans, threshold=0.75)
                    if fuzzy_match:
                        official_entry = next((x for x in official_products if x['clean'] == fuzzy_match), None)
                        if official_entry:
                            product_stats[official_entry['name']] += qty
                            match_found = True
            if not match_found and clean_prod:
                product_stats[clean_prod.title()] += qty

    # --- 4. CALCULATE WINNERS ---
    stats_list = list(stats.values())
    
    # Calculate Winners
    winner_visits = max(stats_list, key=lambda x: x['visits']) if stats_list else None
    winner_trans = max(stats_list, key=lambda x: x['trans']) if stats_list else None
    winner_revenue = max(stats_list, key=lambda x: x['rev']) if stats_list else None
    
    eligible_conv = [s for s in stats_list if s['visits'] > 0]
    winner_conv = max(eligible_conv, key=lambda x: x['trans'] / x['visits']) if eligible_conv else None
    
    best_prod_name = max(product_stats, key=product_stats.get) if product_stats else "N/A"
    best_prod_qty = product_stats[best_prod_name] if product_stats else 0

    # --- 5. FORMAT OUTPUT ---
    return {
        "period": {"start": start_date, "end": end_date},
        "most_completed_visits": winner_visits,
        "most_transactions": winner_trans,
        "highest_revenue": winner_revenue,
        "best_conversion_rate": winner_conv,
        "most_popular_product": {"name": best_prod_name, "qty": best_prod_qty}
    }

def fetch_product_stats_in_period(product_name_clean: str, start_date: str, end_date: str):
    """
    Helper to fetch Qty and Revenue for a specific normalized product name 
    within a date range.
    """
    # We use LIKE with the normalized name to catch variations
    # Note: We rely on the caller to have already fuzzy-matched 'product_name_clean' to a valid official name
    query = text("""
        SELECT SUM(qty) as total_qty, SUM(amount) as total_revenue
        FROM transactions
        WHERE product LIKE :prod_name
            AND inv_date BETWEEN :start AND :end
    """)
    
    # Add wildcards for containment logic (similar to your other tools)
    search_term = f"%{product_name_clean}%"
    
    with engine.connect() as conn:
        result = conn.execute(query, {
            "prod_name": search_term, 
            "start": start_date, 
            "end": end_date
        }).fetchone()
        
        qty = int(result.total_qty) if result.total_qty else 0
        revenue = int(result.total_revenue) if result.total_revenue else 0
        
    return qty, revenue

def get_location_type_and_validate(locations: List[str]):
    """
    Determines if the input list consists of Cities or Provinces.
    Enforces that all inputs must be of the same type.
    Returns: ('city'|'province'|'mixed'|'unknown', normalized_values)
    """
    if not locations:
        return 'empty', []

    # clean inputs
    clean_inputs = [x.strip().title() for x in locations if x.strip()]
    if not clean_inputs:
        return 'empty', []

    # 1. Fetch known locations from DB
    known_cities = set()
    known_provinces = set()
    
    with engine.connect() as conn:
        # Fetch Cities
        res_city = conn.execute(text("SELECT DISTINCT city FROM acc_customers WHERE city IS NOT NULL"))
        for row in res_city:
            known_cities.add(str(row.city).strip().title())
            
        # Fetch Provinces
        res_prov = conn.execute(text("SELECT DISTINCT province FROM acc_customers WHERE province IS NOT NULL"))
        for row in res_prov:
            known_provinces.add(str(row.province).strip().title())

    # 2. Check Matches
    is_city = []
    is_province = []
    
    final_values = []

    for loc in clean_inputs:
        # exact match check
        if loc in known_cities:
            is_city.append(True)
            final_values.append(loc)
        elif loc in known_provinces:
            is_province.append(True)
            final_values.append(loc)
        else:
            # Fuzzy fallback
            match_city = difflib.get_close_matches(loc, list(known_cities), n=1, cutoff=0.85)
            match_prov = difflib.get_close_matches(loc, list(known_provinces), n=1, cutoff=0.85)
            
            if match_city:
                is_city.append(True)
                final_values.append(match_city[0])
            elif match_prov:
                is_province.append(True)
                final_values.append(match_prov[0])
            else:
                # Assuming unknown is a typo, we keep it as is, but tag as unknown
                final_values.append(loc)

    # 3. Determine Type
    if any(is_city) and any(is_province):
        return 'mixed', final_values
    if any(is_city):
        return 'city', final_values
    if any(is_province):
        return 'province', final_values
        
    return 'unknown', final_values

# ==========================================
# 4. MCP TOOLS
# ==========================================

@mcp.tool()
def fetch_deduplicated_visit_report() -> List[Dict]:
    """
    Retrieves a consolidated report of 'Planned Visits' grouped by Customer.
    Aggregates counts by resolving customers to their official 'acc_customers' identity.
    """
    # 1. Get Visit Counts from Plans (grouped by customers.id)
    visit_counts = defaultdict(int)
    query_plans = text("SELECT custcode, COUNT(*) as c FROM plans GROUP BY custcode")
    with engine.connect() as conn:
        for row in conn.execute(query_plans):
            if row.custcode:
                visit_counts[str(row.custcode)] = row.c

    # 2. Load Directory from 'customers' table (Source of the ID in plans)
    internal_customers = load_customer_directory()

    # 3. Load Maps from 'acc_customers' (The Truth)
    map_name_to_cid = load_name_to_cid_map()
    map_cid_to_name = load_acc_cid_map()
    
    available_cid_names = list(map_name_to_cid.keys())

    # 4. Aggregate Logic
    cid_counts = defaultdict(int)
    final_display_names = {} 

    for cust in internal_customers:
        internal_id = cust['id']
        raw_name = cust['name']
        clean_name = cust['clean']
        
        count = visit_counts.get(internal_id, 0)
        if count == 0: continue

        # Try to resolve to a CID
        found_cid = map_name_to_cid.get(clean_name)
        
        # If no exact match, try fuzzy match against acc_customers names
        if not found_cid:
            match = get_fuzzy_match(clean_name, available_cid_names, threshold=0.88)
            if match: 
                found_cid = map_name_to_cid[match]
        
        if found_cid: 
            # Aggregation Success: Add to the official CID bucket
            cid_counts[found_cid] += count
            # Ensure we have the display name set
            if found_cid not in final_display_names:
                final_display_names[found_cid] = map_cid_to_name.get(found_cid, raw_name)
        else: 
            # Fallback: No CID found, keep as is (prefixed to indicate issue)
            key = f"[No CID] {internal_id}"
            cid_counts[key] += count
            final_display_names[key] = f"{raw_name} (Not in ACC-DB)"

    # 5. Build Final Result List
    final_rows = []
    for k, v in cid_counts.items():
        display_name = final_display_names.get(k, "Unknown")
        final_rows.append({
            "id": k, 
            "name": display_name, 
            "count": v
        })
        
    # 6. Sort by Visit Count Descending
    final_rows.sort(key=lambda x: x['count'], reverse=True)

    # 7. Limit to Top 50 to prevent Context Overflow
    return final_rows[:50]

@mcp.tool()
def fetch_deduplicated_sales_report(start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Retrieves a consolidated Sales Performance Report grouped by Salesman.
    Can be filtered by a date range.

    Parameters:
        start_date (str, optional): YYYY-MM-DD. Defaults to '2015-01-01'.
        end_date (str, optional): YYYY-MM-DD. Defaults to today.
    """
    # 1. Apply Date Logic
    final_start, final_end = get_default_dates(start_date, end_date)

    id_map, code_map, digit_map, name_list = load_official_users_map()
    
    query = text("""
        SELECT salesman_name, COUNT(*) as c 
        FROM transactions 
        WHERE inv_date BETWEEN :start AND :end
        GROUP BY salesman_name
    """)
    
    official_counts = defaultdict(int)
    unmatched_counts = defaultdict(int)
    
    with engine.connect() as conn:
        for row in conn.execute(query, {"start": final_start, "end": final_end}):
            raw_field = str(row.salesman_name)
            count = row.c
            parts = re.split(r'[/\&,]', raw_field)
            for part in parts:
                part = part.strip()
                if not part: continue
                resolved_id = resolve_salesman_identity(part, code_map, digit_map, name_list)
                if resolved_id: 
                    official_counts[resolved_id] += count
                else:
                    core_unmatched = clean_salesman_name(part)
                    if not core_unmatched: core_unmatched = part.strip()
                    unmatched_counts[core_unmatched.title()] += count

    output_rows = []
    for user_id, total in official_counts.items():
        user = id_map.get(user_id)
        if user: output_rows.append({"user_id": user['code'], "name": user['name'], "count": total})
    for name, total in unmatched_counts.items():
        output_rows.append({"user_id": "[NO CODE]", "name": name, "count": total})
    
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    # --- RETURN LIST[DICT] ---
    return output_rows

@mcp.tool()
def fetch_transaction_report_by_customer_name(start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Retrieves transaction counts grouped by standardized Customer ID (CID).
    Can be filtered by a date range.

    Parameters:
        start_date (str, optional): YYYY-MM-DD. Defaults to '2015-01-01'.
        end_date (str, optional): YYYY-MM-DD. Defaults to today.
    """
    final_start, final_end = get_default_dates(start_date, end_date)

    query = text("""
        SELECT cust_id, salesman_name, COUNT(*) as c 
        FROM transactions 
        WHERE cust_id IS NOT NULL 
            AND cust_id != '' 
            AND inv_date BETWEEN :start AND :end
        GROUP BY cust_id, salesman_name
    """)
    
    map_cid_to_name = load_acc_cid_map()
    
    results = []
    
    with engine.connect() as conn:
        for row in conn.execute(query, {"start": final_start, "end": final_end}):
            raw_cid = str(row.cust_id)
            raw_salesman = str(row.salesman_name) if row.salesman_name else "Unknown"
            count = row.c
            
            std_cid = standardize_customer_id(raw_cid)
            
            display_name = map_cid_to_name.get(std_cid, f"Unknown ({std_cid})")
            
            results.append({
                "id": std_cid,
                "name": display_name,
                "salesman": raw_salesman,
                "count": count
            })

    # 3. Sort by Count Descending
    results.sort(key=lambda x: x['count'], reverse=True)
    
    return results

@mcp.tool()
def fetch_visit_plans_by_salesman() -> List[Dict]:
    """
    Retrieves the count of 'Planned Visits' grouped by Salesman.
    """
    id_map, _, _, _ = load_official_users_map()
    query = text("SELECT userid, COUNT(*) as c FROM plans GROUP BY userid")
    output_rows = []
    with engine.connect() as conn:
        for row in conn.execute(query):
            u_id = str(row.userid)
            user = id_map.get(u_id)
            if user:
                output_rows.append({"user_id": user['code'], "name": user['name'], "count": row.c})
            else:
                output_rows.append({"user_id": f"ID {u_id}", "name": "[Unknown User]", "count": row.c})
    
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    return output_rows

@mcp.tool()
def fetch_transaction_report_by_product(start_date: str = None, end_date: str = None) -> List[Dict]:
    """
    Retrieves sales performance grouped by Product (Units Sold & Revenue).
    Can be filtered by a date range.

    Parameters:
        start_date (str, optional): YYYY-MM-DD. Defaults to '2015-01-01'.
        end_date (str, optional): YYYY-MM-DD. Defaults to today.
    """
    final_start, final_end = get_default_dates(start_date, end_date)

    id_to_name, official_products = load_product_directory()
    official_products.sort(key=lambda x: len(x['clean']), reverse=True)
    target_clean_names = [x['clean'] for x in official_products]
    
    query = text("""
        SELECT product, SUM(qty) as units, CAST(SUM(amount) AS DECIMAL(65, 0)) as revenue 
        FROM transactions 
        WHERE inv_date BETWEEN :start AND :end
        GROUP BY product
    """)
    
    grouped_data = defaultdict(lambda: {"count": 0, "revenue": 0})
    
    with engine.connect() as conn:
        for row in conn.execute(query, {"start": final_start, "end": final_end}):
            raw_name = str(row.product) if row.product else ""
            units = int(row.units) if row.units else 0
            revenue = int(row.revenue) if row.revenue else 0
            
            clean_raw = normalize_product_name(raw_name)
            target_official_name = None
            
            if clean_raw:
                for official in official_products:
                    if official['clean'] in clean_raw:
                        target_official_name = official['name']
                        break 
                
                if not target_official_name:
                    match_clean = get_fuzzy_match(clean_raw, target_clean_names, threshold=0.75)
                    if match_clean:
                        official_entry = next((x for x in official_products if x['clean'] == match_clean), None)
                        if official_entry:
                            target_official_name = official_entry['name']
            
            if not target_official_name:
                clean_display = clean_raw.title() if clean_raw else "[Unknown Product]"
                target_official_name = f"[Uncategorized] {clean_display}"

            grouped_data[target_official_name]["count"] += units
            grouped_data[target_official_name]["revenue"] += revenue

    output_rows = []
    for name, data in grouped_data.items():
        output_rows.append({
            "name": name, 
            "units": data["count"], 
            "revenue": data["revenue"]
        }) 
        
    output_rows.sort(key=lambda x: int(float(x['revenue'])), reverse=True)
    
    return output_rows

@mcp.tool()
def fetch_visit_plans_by_clinic() -> List[Dict]:
    """
    Retrieves 'Planned Visits' grouped by Clinic, distinguishing branches by City.
    """
    city_buckets = load_clinic_directory()
    query = text("SELECT cliniccode, COUNT(*) as c FROM plans GROUP BY cliniccode")
    visit_counts = defaultdict(int)
    
    with engine.connect() as conn:
        for row in conn.execute(query):
            visit_counts[str(row.cliniccode)] = row.c
            
    final_output = []
    for bucket_key, clinics in city_buckets.items():
        grouped_map = defaultdict(list)
        clinics.sort(key=lambda x: len(x['clean']), reverse=True)
        for clinic in clinics:
            core_name = clinic['clean']
            if not core_name: continue 
            potential_matches = list(grouped_map.keys())
            match = get_fuzzy_match(core_name, potential_matches, threshold=0.88)
            if match: grouped_map[match].append(clinic)
            else: grouped_map[core_name].append(clinic)
        
        for clean_key, entries in grouped_map.items():
            ids = [x['id'] for x in entries]
            total_visits = sum(visit_counts.get(cid, 0) for cid in ids)
            if total_visits > 0:
                display_name = max((x['name'] for x in entries), key=len)
                display_city = entries[0]['city_display']
                final_output.append({
                    "ids": ", ".join(ids), "name": display_name, "city": display_city, "count": total_visits
                })

    final_output.sort(key=lambda x: x['count'], reverse=True)
    
    return final_output

@mcp.tool()
def fetch_report_counts_by_salesman() -> List[Dict]:
    """
    Retrieves the count of *Completed* Visits (Reports) grouped by Salesman.
    """
    id_map, _, _, _ = load_official_users_map()
    query = text("SELECT p.userid, COUNT(r.id) as c FROM reports r JOIN plans p ON r.idplan = p.id GROUP BY p.userid")
    output_rows = []
    with engine.connect() as conn:
        for row in conn.execute(query):
            u_id = str(row.userid)
            user = id_map.get(u_id)
            if user:
                output_rows.append({"user_id": user['code'], "name": user['name'], "count": row.c})
            else:
                output_rows.append({"user_id": f"ID {u_id}", "name": "[Unknown User]", "count": row.c})
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    return output_rows

@mcp.tool()
def fetch_comprehensive_salesman_performance() -> List[Dict]:
    """
    Retrieves a 360-degree 'Scorecard' for Salesmen (Plans vs Visits vs Sales).
    """
    id_map, code_map, digit_map, name_list = load_official_users_map()
    master_data = defaultdict(lambda: {'plans': 0, 'reports': 0, 'transactions': 0})

    # Plans
    with engine.connect() as conn:
        for row in conn.execute(text("SELECT userid, COUNT(*) as c FROM plans GROUP BY userid")):
            if str(row.userid) in id_map: master_data[str(row.userid)]['plans'] += row.c
    
    # Reports
    with engine.connect() as conn:
        for row in conn.execute(text("SELECT p.userid, COUNT(r.id) as c FROM reports r JOIN plans p ON r.idplan = p.id GROUP BY p.userid")):
            if str(row.userid) in id_map: master_data[str(row.userid)]['reports'] += row.c

    # Transactions
    with engine.connect() as conn:
        for row in conn.execute(text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")):
            parts = re.split(r'[/\&,]', str(row.salesman_name))
            for part in parts:
                part = part.strip()
                if not part: continue
                resolved_id = resolve_salesman_identity(part, code_map, digit_map, name_list)
                if resolved_id: master_data[resolved_id]['transactions'] += row.c

    output_rows = []
    for uid, stats in master_data.items():
        user = id_map.get(uid)
        if not user: continue
        plans, reports, trans = stats['plans'], stats['reports'], stats['transactions']
        ratio_pv = (reports / plans) if plans > 0 else 0.0
        ratio_vt = (trans / reports) if reports > 0 else (float(trans) if trans > 0 else 0.0)
        output_rows.append({
            "code": user['code'], "name": user['name'],
            "plans": plans, "reports": reports, "transactions": trans,
            "ratio_pv": round(ratio_pv, 2), "ratio_vt": round(ratio_vt, 2)
        })

    output_rows.sort(key=lambda x: x['transactions'], reverse=True)
    
    return output_rows

@mcp.tool()
def fetch_salesman_visit_history(salesman_name: str) -> Dict[str, Any]:
    """
    Fetches detailed visit notes and transaction stats for a SPECIFIC salesman.

    Description:
        Used for deep-dive analysis of a single salesman's performance.
        1. Identifies the salesman ID from the input name.
        2. Fetches their total transaction count (using identity resolution).
        3. Fetches their recent 'visitnote' entries from the reports table.
    
    Parameters:
        salesman_name (str): The name of the salesman (e.g., "Wilson", "Gladys").

    Returns:
        str: JSON formatted data including total transactions and recent visit notes.

    When to use:
        Use when the user asks "Why are [Name]'s sales low?", "Analyze [Name]'s visits", 
        or "Check the effectiveness of [Name]".
    """

    return fetch_single_salesman_data(salesman_name)

@mcp.tool()
def fetch_salesman_comparison_data(salesman_a: str, salesman_b: str) -> Dict[str, Any]:
    """
    Fetches side-by-side visit notes and transaction stats for TWO salesmen.

    Description:
        Designed for comparative analysis.
        1. Resolves identities for both Salesman A and Salesman B.
        2. Fetches transaction counts and visit notes for BOTH.
        3. Combines them into a single report for the LLM to analyze.

    Parameters:
        salesman_a (str): Name/Code of the first salesman.
        salesman_b (str): Name/Code of the second salesman.

    Returns:
        str: JSON formatted data with separate sections for Salesman A and B.

    When to use:
        Use when the user asks to "compare Wilson and Gladys", "who is better between A and B"
        or "compare visit effectiveness of A vs B".
    """
    report_a = fetch_single_salesman_data(salesman_a)
    report_b = fetch_single_salesman_data(salesman_b)
    
    return {"salesman_a": report_a, "salesman_b": report_b}

@mcp.tool()
def fetch_best_performers(start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Fetches a leaderboard of best performing salesmen and products within a date range or overall.
    
    Description:
        Identifies the top performers across four categories:
        1. Visit Volume (Most visits completed).
        2. Transaction Volume (Most sales transactions).
        3. Revenue Generation (Highest total sales value).
        4. Conversion Efficiency (Highest ratio of Transactions to Visits).
        5. Also identifies the single most sold product by quantity.
    
    Parameters:
        start_date (str, optional): Start date (YYYY-MM-DD). Defaults to '2015-01-01' if not provided.
        end_date (str, optional): End date (YYYY-MM-DD). Defaults to today (GMT+7) if not provided.

    Returns:
        str: JSON formatted leaderboard.

    When to use:
        Use when the user asks "Who is the best salesman?", "Show me the top performers for January",
        or "Who had the highest conversion rate last year?".
    """
    tz = pytz.timezone('Asia/Jakarta')
    today = datetime.datetime.now(tz).strftime('%Y-%m-%d')
    final_start = start_date if start_date and start_date.strip() else '2015-01-01'
    final_end = end_date if end_date and end_date.strip() else today
    
    return fetch_best_performers_logic(final_start, final_end)

@mcp.tool()
def fetch_transaction_counts_by_user_level(target_levels: str = None) -> Dict[str, Any]:
    """
    Calculates the number of transactions grouped by User Level (e.g., DC, TS, AM, NULL).

    Description:
        1. Loads all users and their assigned levels (DC, TS, SU, etc.).
        2. Fetches all transactions.
        3. Resolves the messy 'salesman_name' in transactions to a specific User ID.
        4. Looks up the Level for that User ID.
        5. Aggregates the count of transactions per Level.
        6. Filters the output based on the requested 'target_levels'.

    Parameters:
        target_levels (str, optional): A comma-separated string of levels to filter by. 
        Examples: "DC", "TS", "DC, TS", "NULL". 
        If None or empty, returns ALL levels.

    Returns:
        str: A JSON formatted table of transaction counts by User Level.

    When to use:
        Use when the user asks "How many transactions for DC salesmen?", 
        "Compare transactions between DC and TS", or "Show transactions for users with no level".
    """
    # 1. Load Data
    id_map, code_map, digit_map, name_list = load_official_users_map()
    
    # 2. Parse Filter
    filters = []
    if target_levels:
        filters = [x.strip().upper() for x in target_levels.split(',') if x.strip()]

    # 3. Aggregate Counts
    level_counts = defaultdict(int)
    
    query = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
    
    with engine.connect() as conn:
        for row in conn.execute(query):
            raw_field = str(row.salesman_name)
            count = row.c
            parts = re.split(r'[/\&,]', raw_field)
            for part in parts:
                part = part.strip()
                if not part: continue
                resolved_id = resolve_salesman_identity(part, code_map, digit_map, name_list)
                user_level = "UNKNOWN"
                if resolved_id:
                    user_level = id_map[resolved_id].get('level', "NULL")
                else:
                    user_level = "UNIDENTIFIED"
                level_counts[user_level] += count

    # 4. Filter and Format Results
    final_rows = []
    total_filtered_count = 0

    for level, count in level_counts.items():
        if not filters or level in filters:
            final_rows.append({"category": level, "count": count})
            total_filtered_count += count

    final_rows.sort(key=lambda x: x['count'], reverse=True)

    return {
        "breakdown": final_rows,
        "total_filtered": total_filtered_count,
        "filters_applied": filters if filters else "ALL"
    }

@mcp.tool()
def analyze_product_sales_growth(
    product_name: str, 
    period1_start: str, 
    period1_end: str, 
    period2_start: str, 
    period2_end: str
) -> Dict[str, Any]:
    """
    Analyzes the sales growth of a specific product between two time periods.

    Description:
        1. Identifies the official product name (correcting typos).
        2. Fetches Total Units Sold and Revenue for Period 1.
        3. Fetches Total Units Sold and Revenue for Period 2.
        4. Calculates the percentage growth (or decline).
        5. Returns a detailed Markdown analysis.

    Parameters:
        product_name (str): The name of the product (e.g., "Angel Aligner").
        period1_start (str): Start date of the older/first period (YYYY-MM-DD).
        period1_end (str): End date of the older/first period (YYYY-MM-DD).
        period2_start (str): Start date of the newer/second period (YYYY-MM-DD).
        period2_end (str): End date of the newer/second period (YYYY-MM-DD).

    Returns:
        str: A JSON formatted report analyzing the sales growth of the product.
    """
    # 1. Identify Product
    id_to_name, official_products = load_product_directory()
    target_clean_names = [x['clean'] for x in official_products]
    
    input_clean = normalize_product_name(product_name)
    match_clean = get_fuzzy_match(input_clean, target_clean_names, threshold=0.70)
    
    if not match_clean:
        for official in official_products:
            if input_clean in official['clean']:
                match_clean = official['clean']
                break
    
    if not match_clean:
        return {"error": f"Could not find product matching '{product_name}'."}

    official_entry = next((x for x in official_products if x['clean'] == match_clean), None)
    display_name = official_entry['name'] if official_entry else product_name.title()

    # 2. Fetch Data
    qty_p1, rev_p1 = fetch_product_stats_in_period(match_clean, period1_start, period1_end)
    qty_p2, rev_p2 = fetch_product_stats_in_period(match_clean, period2_start, period2_end)

    # 3. Calculate Growth
    if qty_p1 > 0:
        qty_growth = ((qty_p2 - qty_p1) / qty_p1) * 100
    else:
        qty_growth = 100.0 if qty_p2 > 0 else 0.0

    if rev_p1 > 0:
        rev_growth = ((rev_p2 - rev_p1) / rev_p1) * 100
    else:
        rev_growth = 100.0 if rev_p2 > 0 else 0.0

    trend_text = "Growth" if qty_growth > 0 else ("Decline" if qty_growth < 0 else "Stagnant")

    # 5. Format Output (Return DICT)
    return {
        "product": display_name,
        "period_1": {
            "start": period1_start,
            "end": period1_end,
            "units": qty_p1,
            "revenue": rev_p1
        },
        "period_2": {
            "start": period2_start,
            "end": period2_end,
            "units": qty_p2,
            "revenue": rev_p2
        },
        "growth": {
            "units_percent": round(qty_growth, 2),
            "revenue_percent": round(rev_growth, 2),
            "trend": trend_text
        }
    }

@mcp.tool()
def fetch_customer_count_by_location() -> List[Dict]:
    """
    Retrieves customer counts grouped by Province only (to reduce dataset size).
    """
    query = text("""
        SELECT province, COUNT(*) as c 
        FROM acc_customers 
        GROUP BY province
    """)
    
    results = []
    with engine.connect() as conn:
        for row in conn.execute(query):
            province = str(row.province).strip() if row.province else "Unspecified"
            if province == "": province = "Unspecified"
            
            results.append({
                "province": province,
                "count": row.c
            })
            
    # Sort by Count Descending (Most populated provinces first)
    results.sort(key=lambda x: x['count'], reverse=True)
    return results

@mcp.tool()
def fetch_transactions_by_location(location_query: str = None) -> Union[List[Dict], Dict]:
    """
    Displays transaction counts for a specific location grouped by product.
    Can handle multiple locations of the same type (comma-separated).
    If no location is provided, returns data grouped by Province.
    """
    # 1. Parse Input
    target_locations = []
    if location_query:
        target_locations = [x.strip() for x in location_query.split(',') if x.strip()]
    
    # 2. Determine Location Type
    loc_type, cleaned_locations = get_location_type_and_validate(target_locations)
    
    if loc_type == 'mixed':
        return {"error": "You can only enter multiple locations of the same type (e.g., all cities or all provinces)."}
    
    # 3. Build Query Based on Type
    # If empty or unknown, default to All Provinces
    group_col = "a.province"
    where_clause = ""
    params = {}
    
    if loc_type == 'city':
        group_col = "a.city"
        where_clause = "WHERE a.city IN :locs"
        params = {"locs": cleaned_locations}
    elif loc_type == 'province':
        group_col = "a.province"
        where_clause = "WHERE a.province IN :locs"
        params = {"locs": cleaned_locations}
    else:
        # Default case: No filter, group by Province
        group_col = "a.province"
        where_clause = "WHERE a.province IS NOT NULL AND a.province != ''"
        params = {}

    sql = f"""
        SELECT {group_col} as location_name, t.product, SUM(t.qty) as units 
        FROM transactions t
        JOIN acc_customers a ON t.cust_id = a.cid
        {where_clause}
        GROUP BY {group_col}, t.product
    """
    
    # 4. Execute and Normalize Products (Reusing logic from fetch_transaction_report_by_product)
    id_to_name, official_products = load_product_directory()
    official_products.sort(key=lambda x: len(x['clean']), reverse=True)
    target_clean_names = [x['clean'] for x in official_products]
    
    grouped_data = defaultdict(lambda: {"count": 0})
    
    with engine.connect() as conn:
        # Handle IN clause for lists
        if params and 'locs' in params:
            # SqlAlchemy text() with IN clause requires passing tuple/list directly
            result = conn.execute(text(sql).bindparams(locs=tuple(cleaned_locations)))
        else:
            result = conn.execute(text(sql))
            
        for row in result:
            loc_name = str(row.location_name).strip()
            raw_prod = str(row.product)
            units = int(row.units)
            
            # --- Product Normalization Logic ---
            clean_raw = normalize_product_name(raw_prod)
            target_official_name = None
            
            if clean_raw:
                for official in official_products:
                    if official['clean'] in clean_raw:
                        target_official_name = official['name']
                        break 
                if not target_official_name:
                    match_clean = get_fuzzy_match(clean_raw, target_clean_names, threshold=0.75)
                    if match_clean:
                        official_entry = next((x for x in official_products if x['clean'] == match_clean), None)
                        if official_entry:
                            target_official_name = official_entry['name']
            
            if not target_official_name:
                clean_display = clean_raw.title() if clean_raw else "[Unknown Product]"
                target_official_name = f"[Uncategorized] {clean_display}"
            # -----------------------------------

            # Key: Location + Product
            key = (loc_name, target_official_name)
            grouped_data[key]["count"] += units

    # 5. Format Output
    output = []
    for (loc, prod), data in grouped_data.items():
        output.append({
            "location": loc,
            "product_name": prod,
            "transaction_count": data["count"]
        })
        
    # Sort by Location then Count
    output.sort(key=lambda x: (x['location'], x['transaction_count']), reverse=True)
    
    return output

# ==========================================
# 5. FASTAPI INTEGRATION & REST ENDPOINTS
# ==========================================

# Lifecycle Manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- BAM Analytics Server Starting ---")
    yield
    print("--- Server Shutting Down ---")

# Initialize FastAPI app
app = FastAPI(
    title="BAM Analytics Server",
    description="BAM MCP Server exposing Sales Analytics tools and endpoints.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware - allow only the specified origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ollama.ctbacloud.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

# Mount MCP Server through SSE
app.mount("/mcp", mcp.sse_app())

# API Endpoints
@app.get("/")
async def root():
    return {"message": "BAM MCP Server is running. Access MCP at /mcp/sse"}

@app.get("/visits/customers")
def get_visits_by_customer():
    return fetch_deduplicated_visit_report()

@app.get("/visits/salesmen")
def get_visits_by_salesman():
    return fetch_visit_plans_by_salesman()

@app.get("/visits/clinics")
def get_visits_by_clinic():
    return fetch_visit_plans_by_clinic()

@app.get("/transactions/customers")
def get_transactions_by_customer(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    return fetch_transaction_report_by_customer_name(start_date, end_date)

@app.get("/transactions/salesmen")
def get_transactions_by_salesman(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    return fetch_deduplicated_sales_report(start_date, end_date)

@app.get("/transactions/products")
def get_transactions_by_product(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    return fetch_transaction_report_by_product(start_date, end_date)

@app.get("/transactions/levels")
def get_transactions_by_level(levels: Optional[str] = Query(None, description="Comma-separated levels (DC, TS, NULL)")):
    return fetch_transaction_counts_by_user_level(levels)

@app.get("/reports/salesmen")
def get_reports_by_salesman():
    return fetch_report_counts_by_salesman()

@app.get("/performance/salesmen")
def get_salesman_performance_scorecard():
    return fetch_comprehensive_salesman_performance()

@app.get("/performance/best")
def get_best_performers(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    return fetch_best_performers(start_date, end_date)

@app.get("/analysis/salesman/{name}")
def analyze_salesman_effectiveness(name: str):
    return fetch_salesman_visit_history(name)

@app.get("/analysis/compare")
def compare_salesmen(salesman_a: str, salesman_b: str):
    return fetch_salesman_comparison_data(salesman_a, salesman_b)

@app.get("/analysis/growth/product")
def get_product_growth_analysis(
    product: str,
    p1_start: str, p1_end: str,
    p2_start: str, p2_end: str
):
    return analyze_product_sales_growth(product, p1_start, p1_end, p2_start, p2_end)

@app.get("/customers/location")
def get_customers_by_location():
    return fetch_customer_count_by_location()

@app.get("/transactions/location")
def get_transactions_by_location(
    location: Optional[str] = Query(None, description="Comma-separated cities or provinces")
):
    return fetch_transactions_by_location(location)

@app.get("/tools")
async def list_tools():
    """
    Simple endpoint to list all registered tools with their input schemas.
    """
    tools_data = []
    
    source = None
    if hasattr(mcp, '_tool_manager') and hasattr(mcp._tool_manager, '_tools'):
        source = mcp._tool_manager._tools
    elif hasattr(mcp, '_tools'):
        source = mcp._tools
        
    if source:
        for name, tool in source.items():
            schema = "Unknown Schema"
            
            if hasattr(tool, "parameters"):
                if hasattr(tool.parameters, "model_json_schema"):
                    schema = tool.parameters.model_json_schema()
                else:
                    schema = tool.parameters
            
            tools_data.append({
                "name": getattr(tool, "name", name),
                "description": getattr(tool, "description", ""),
                "input_schema": schema
            })
            
    return {
        "count": len(tools_data),
        "tools": tools_data
    }

# ==========================================
# 6. ENTRY POINT
# ==========================================

# Run the MCP server
if __name__ == "__main__":
    print("Starting BAM MCP Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)