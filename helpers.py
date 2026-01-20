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

def fetch_single_salesman_data(salesman_name: str) -> str:
    """
    Retrieves transaction count and visit notes for a single salesman.
    Used by analysis tools to generate reports.
    """
    # 1. Identify Salesman
    target_id, official_name = find_salesman_id_by_name(salesman_name)
    
    if not target_id:
        return f"Error: Could not find salesman '{salesman_name}'. Please check the name or code."

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
        ORDER BY r.id DESC
        LIMIT 50
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query_notes, {"uid": target_id})
        for row in result:
            if row.visitnote and str(row.visitnote).strip():
                visit_notes.append(f"- {str(row.visitnote).strip()}")

    total_visits = len(visit_notes)
    
    # Format Output
    output = f"=== DATA FOR: {official_name} (ID: {target_id}) ===\n"
    output += f"Total Transactions: {transaction_count}\n"
    output += f"Total Visit Reports: {total_visits}\n"
    output += "Recent Visit Notes:\n"
    if visit_notes:
        output += "\n".join(visit_notes)
    else:
        output += "(No notes found)"
    output += "\n" + "="*40 + "\n"
    
    return output

def fetch_best_performers_logic(start_date: str, end_date: str) -> str:
    """
    Executes multiple queries to determine the best performers in various categories
    within a date range.
    """
    stats = {} # {salesman_name: {'visits': 0, 'trans_count': 0, 'revenue': 0}}
    top_product = "N/A"
    
    with engine.connect() as conn:
        # 1. Fetch Visit Counts (linked via plans -> users)
        visit_query = text("""
            SELECT u.name, COUNT(r.id) as visit_count
            FROM reports r
            JOIN plans p ON r.idplan = p.id
            JOIN users u ON p.userid = u.id
            WHERE p.date BETWEEN :start AND :end
            GROUP BY u.name
        """)
        
        result_visits = conn.execute(visit_query, {"start": start_date, "end": end_date})
        for row in result_visits:
            name = row.name
            if name not in stats:
                stats[name] = {'visits': 0, 'trans_count': 0, 'revenue': 0}
            stats[name]['visits'] = row.visit_count

        # 2. Fetch Transaction Counts & Revenue
        trans_query = text("""
            SELECT salesman_name, COUNT(*) as t_count, SUM(amount * qty) as revenue
            FROM transactions
            WHERE inv_date BETWEEN :start AND :end
            GROUP BY salesman_name
        """)
        
        result_trans = conn.execute(trans_query, {"start": start_date, "end": end_date})
        for row in result_trans:
            name = row.salesman_name
            if name: # Ensure name is not None
                if name not in stats:
                    stats[name] = {'visits': 0, 'trans_count': 0, 'revenue': 0}
                stats[name]['trans_count'] = row.t_count
                stats[name]['revenue'] = row.revenue

        # 3. Fetch Most Sold Product
        prod_query = text("""
            SELECT prodname, SUM(qty) as total_qty
            FROM transactions
            WHERE inv_date BETWEEN :start AND :end
            GROUP BY product
            ORDER BY total_qty DESC
            LIMIT 1
        """)
        result_prod = conn.execute(prod_query, {"start": start_date, "end": end_date}).fetchone()
        if result_prod:
            top_product = f"{result_prod.prodname} ({result_prod.total_qty} units)"

    # --- Determine Winners ---
    if not stats:
        return f"No performance data found between {start_date} and {end_date}."

    winner_visits = max(stats.items(), key=lambda x: x[1]['visits'])
    winner_trans_count = max(stats.items(), key=lambda x: x[1]['trans_count'])
    winner_revenue = max(stats.items(), key=lambda x: x[1]['revenue'])
    
    # Calculate Conversion Ratio (Transactions / Visits)
    # Filter out those with 0 visits to avoid ZeroDivisionError
    valid_ratios = {
        k: (v['trans_count'] / v['visits']) * 100 
        for k, v in stats.items() 
        if v['visits'] > 0
    }
    
    if valid_ratios:
        winner_conversion = max(valid_ratios.items(), key=lambda x: x[1])
        conv_str = f"**{winner_conversion[0]}** with {winner_conversion[1]:.2f}%"
    else:
        conv_str = "No valid visits recorded to calculate conversion."

    # --- Format Output ---
    report = f"""
### 🏆 Best Performers Report
**Period:** {start_date} to {end_date}

| Category | Winner | Stat |
| :--- | :--- | :--- |
| **Highest Visit Count** | **{winner_visits[0]}** | {winner_visits[1]['visits']} visits |
| **Highest Transaction Count** | **{winner_trans_count[0]}** | {winner_trans_count[1]['trans_count']} transactions |
| **Highest Revenue** | **{winner_revenue[0]}** | ${winner_revenue[1]['revenue']:,.2f} |
| **Best Conversion Ratio** | {conv_str} | (Trans / Visits) |

#### 📦 Most Popular Product
**{top_product}**
"""
    return report