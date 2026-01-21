import re
import difflib
from collections import defaultdict
from sqlalchemy import text
from database import engine

# --- STRING NORMALIZATION ---

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
    
    query = text("SELECT id, username, name FROM users")
    with engine.connect() as conn:
        result = conn.execute(query)
        for row in result:
            u_id = str(row.id)
            code = str(row.username).lower().strip() 
            name = row.name
            id_map[u_id] = {"id": u_id, "code": row.username, "name": name}
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

def fetch_single_salesman_data(salesman_name: str, output_format: int = 0):
    """
    Retrieves transaction count and visit notes for a single salesman.
    Used by analysis tools to generate reports. 
    Can generate output in Markdown format (1) or JSON dictionary format (0).
    """
    # 1. Identify Salesman
    target_id, official_name = find_salesman_id_by_name(salesman_name)
    
    if not target_id:
        error_msg = f"Error: Could not find salesman '{salesman_name}'."
        if output_format == 0:
            return {"error": error_msg}
        return error_msg
    
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

    # 3. Get Visit Notes
    visit_notes = []
    query_notes = text("""
        SELECT r.visitnote 
        FROM reports r
        JOIN plans p ON r.idplan = p.id
        WHERE p.userid = :uid
        ORDER BY r.date DESC
        LIMIT 50
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query_notes, {"uid": target_id})
        for row in result:
            if row.visitnote and str(row.visitnote).strip():
                visit_notes.append(f"- {str(row.visitnote).strip()}")

    total_visits = len(visit_notes)
    
    # --- RETURN JSON (Format 0) ---
    if output_format == 0:
        return {
            "id": target_id,
            "name": official_name,
            "total_transactions": transaction_count,
            "total_visits": total_visits,
            "recent_notes": visit_notes
        }
    
    # --- RETURN MARKDOWN (Format 1) ---
    output = f"=== DATA FOR: {official_name} (ID: {target_id}) ===\n"
    output += f"Total Transactions: {transaction_count}\n"
    output += f"Total Visit Reports: {total_visits}\n"
    output += "Recent Visit Notes:\n"
    if visit_notes:
        formatted_notes = [f"- {note}" for note in visit_notes]
        output += "\n".join(formatted_notes)
    else:
        output += "(No notes found)"
    output += "\n" + "="*40 + "\n"
    
    return output

def fetch_best_performers_logic(start_date: str, end_date: str, output_format: int = 0):
    """
    Determines best performers with rigorous Identity Resolution for Salesmen
    and Fuzzy Matching for Products.
    Can generate output in Markdown format (1) or JSON dictionary format (0).
    """
    from sqlalchemy import text
    from collections import defaultdict
    import re

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
    # --- RETURN JSON (Format 0) ---
    if output_format == 0:
        return {
            "period": {"start": start_date, "end": end_date},
            "most_visits": winner_visits if winner_visits else None,
            "most_transactions": winner_trans if winner_trans else None,
            "highest_revenue": winner_revenue if winner_revenue else None,
            "best_conversion": {
                "name": winner_conv['name'],
                "ratio": (winner_conv['trans'] / winner_conv['visits']) * 100
            } if winner_conv else None,
            "popular_product": {
                "name": best_prod_name,
                "qty": best_prod_qty
            }
        }

    # --- RETURN MARKDOWN (Format 1) ---
    conv_str = f"**{winner_conv['name']}** ({(winner_conv['trans'] / winner_conv['visits']) * 100:.2f}%)" if winner_conv else "N/A"
    top_product_str = f"{best_prod_name} ({best_prod_qty} units)"

    md = f"""
### 🏆 Best Performers ({start_date} to {end_date})

| Award Category | Winner | Statistic |
| :--- | :--- | :--- |
| **Most Completed Visits** | **{winner_visits['name'] if winner_visits else '-'}** | {winner_visits['visits'] if winner_visits else 0} Visits |
| **Most Transactions** | **{winner_trans['name'] if winner_trans else '-'}** | {winner_trans['trans'] if winner_trans else 0} Deals |
| **Highest Revenue** | **{winner_revenue['name'] if winner_revenue else '-'}** | Rp {winner_revenue['rev']:,.0f} |
| **Best Conversion Rate** | {winner_conv['name'] if eligible_conv else '-'} | {conv_str} (Visits / Deals) |

#### 📦 Most Popular Product
**{top_product_str}**
"""
    return md