import re
import difflib
from collections import defaultdict
from sqlalchemy import text
from database import engine  # Import engine from our new database file

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

