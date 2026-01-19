import re
from collections import defaultdict
from sqlalchemy import text
from server_instance import mcp
from database import engine
import helpers

# --- MCP TOOLS ---

@mcp.tool()
def fetch_deduplicated_visit_report() -> str:
    """
    Retrieves a consolidated report of 'Planned Visits' grouped by Customer.
    """
    visit_counts = defaultdict(int)
    query_plans = text("SELECT custcode, COUNT(*) as c FROM plans GROUP BY custcode")
    with engine.connect() as conn:
        for row in conn.execute(query_plans):
            visit_counts[str(row.custcode)] = row.c

    customers = []
    query_cust = text("SELECT id, custname, phone FROM customers")
    with engine.connect() as conn:
        for row in conn.execute(query_cust):
            customers.append({
                "id": str(row.id),
                "name": row.custname,
                "phone": row.phone
            })

    grouped_map = defaultdict(list)
    for cust in customers:
        core_name = helpers.normalize_name(cust['name'])
        if not core_name: continue
        potential_matches = [k for k in grouped_map.keys() if k and k[0] == core_name[0]]
        match = helpers.get_fuzzy_match(core_name, potential_matches, threshold=0.92)
        if match:
            grouped_map[match].append(cust)
        else:
            grouped_map[core_name].append(cust)

    final_rows = []
    for core_name, entries in grouped_map.items():
        ids = [x['id'] for x in entries]
        total_visits = sum(visit_counts.get(cust_id, 0) for cust_id in ids)
        display_name = max((x['name'] for x in entries), key=len)
        if total_visits > 0:
            final_rows.append({
                "ids": "; ".join(ids),
                "name": display_name,
                "count": total_visits
            })
    
    final_rows.sort(key=lambda x: x['count'], reverse=True)
    md = "CONSOLIDATED VISIT REPORT (Auto-Deduplicated):\n"
    md += "| Customer ID(s) | Customer Name | Number of Visits |\n"
    md += "| :--- | :--- | :--- |\n"
    for row in final_rows:
        md += f"| {row['ids']} | {row['name']} | {row['count']} |\n"
    return md

@mcp.tool()
def fetch_deduplicated_sales_report() -> str:
    """
    Retrieves a consolidated Sales Performance Report grouped by Salesman.
    """
    id_map, code_map, digit_map, name_list = helpers.load_official_users_map()
    query = text("SELECT salesman_name, COUNT(*) as c FROM transactions GROUP BY salesman_name")
    
    official_counts = defaultdict(int)
    unmatched_counts = defaultdict(int)
    
    with engine.connect() as conn:
        for row in conn.execute(query):
            raw_field = str(row.salesman_name)
            count = row.c
            parts = re.split(r'[/\&,]', raw_field)
            for part in parts:
                part = part.strip()
                if not part: continue
                resolved_id = helpers.resolve_salesman_identity(part, code_map, digit_map, name_list)
                if resolved_id:
                    official_counts[resolved_id] += count
                else:
                    core_unmatched = helpers.clean_salesman_name(part)
                    if not core_unmatched: core_unmatched = part.strip()
                    unmatched_counts[core_unmatched.title()] += count

    output_rows = []
    for user_id, total in official_counts.items():
        user = id_map.get(user_id)
        if user:
            output_rows.append({"user_id": user['code'], "name": user['name'], "count": total})
    for name, total in unmatched_counts.items():
        output_rows.append({"user_id": "[NO CODE]", "name": name, "count": total})
    
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
    Retrieves transaction counts grouped by normalized Customer Name.
    """
    official_customers = helpers.load_customer_directory()
    cid_to_name_map = helpers.load_acc_cid_map()
    query = text("SELECT cust_id, COUNT(*) as c FROM transactions WHERE cust_id IS NOT NULL AND cust_id != '' GROUP BY cust_id")
    
    grouped_data = defaultdict(lambda: {"count": 0, "id": "N/A"})
    with engine.connect() as conn:
        for row in conn.execute(query):
            raw_cid = str(row.cust_id).strip()
            count = row.c
            t_cid = re.sub(r'^[A-Z]-', '', raw_cid)
            acc_name = cid_to_name_map.get(t_cid)
            
            if not acc_name:
                key = f"[Unknown ID] {t_cid}"
                grouped_data[key]["count"] += count
                grouped_data[key]["id"] = t_cid 
                continue
            
            clean_acc_name = helpers.normalize_name(acc_name)
            target_clean_names = [x['clean'] for x in official_customers]
            match_clean = helpers.get_fuzzy_match(clean_acc_name, target_clean_names, threshold=0.85)
            
            if match_clean:
                official_entry = next((x for x in official_customers if x['clean'] == match_clean), None)
                if official_entry:
                    grouped_data[official_entry['name']]["count"] += count
                    grouped_data[official_entry['name']]["id"] = official_entry['id']
            else:
                display_name = f"[New] {clean_acc_name.title()}" if clean_acc_name else acc_name
                grouped_data[display_name]["count"] += count
                grouped_data[display_name]["id"] = t_cid 

    output_rows = []
    for name, data in grouped_data.items():
        output_rows.append({"id": data["id"], "name": name, "count": data["count"]})
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
    Retrieves the count of 'Planned Visits' grouped by Salesman.
    """
    id_map, _, _, _ = helpers.load_official_users_map()
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
    md = "PLANNED VISITS REPORT (Grouped by Salesman):\n"
    md += "| Sales User ID | Sales Name | Visit Count |\n"
    md += "| :--- | :--- | :--- |\n"
    for row in output_rows:
        md += f"| {row['user_id']} | {row['name']} | {row['count']} |\n"
    return md

@mcp.tool()
def fetch_transaction_report_by_product() -> str:
    """
    Retrieves sales performance grouped by Product (Units Sold & Revenue).
    """
    id_to_name, official_products = helpers.load_product_directory()
    official_products.sort(key=lambda x: len(x['clean']), reverse=True)
    target_clean_names = [x['clean'] for x in official_products]
    
    # CAST amount to DECIMAL to avoid floating point errors
    query = text("""
        SELECT item_id, product, 
            SUM(qty) as units, 
            CAST(SUM(amount) AS DECIMAL(65, 0)) as revenue 
        FROM transactions 
        GROUP BY item_id, product
    """)
    grouped_data = defaultdict(lambda: {"count": 0, "revenue": 0})
    
    with engine.connect() as conn:
        for row in conn.execute(query):
            raw_id = str(row.item_id).strip() if row.item_id else ""
            raw_name = str(row.product)
            units = int(row.units) if row.units else 0
            revenue = int(row.revenue) if row.revenue else 0
            
            clean_raw = helpers.normalize_product_name(raw_name)
            match_found = False
            
            if raw_id and raw_id in id_to_name:
                grouped_data[id_to_name[raw_id]]["count"] += units
                grouped_data[id_to_name[raw_id]]["revenue"] += revenue
                match_found = True
            
            if not match_found and clean_raw:
                for official in official_products:
                    if f" {official['clean']} " in f" {clean_raw} ":
                        grouped_data[official['name']]["count"] += units
                        grouped_data[official['name']]["revenue"] += revenue
                        match_found = True
                        break 
            
            if not match_found and clean_raw:
                match_clean = helpers.get_fuzzy_match(clean_raw, target_clean_names, threshold=0.70)
                if match_clean:
                    official_entry = next((x for x in official_products if x['clean'] == match_clean), None)
                    if official_entry:
                        grouped_data[official_entry['name']]["count"] += units
                        grouped_data[official_entry['name']]["revenue"] += revenue
                        match_found = True
            
            if not match_found:
                clean_display = clean_raw.title() if clean_raw else "[Unknown Product]"
                display_name = f"[Uncategorized] {clean_display}"
                grouped_data[display_name]["count"] += units
                grouped_data[display_name]["revenue"] += revenue

    output_rows = []
    for name, data in grouped_data.items():
        output_rows.append({"name": name, "count": data["count"], "revenue": data["revenue"]})
    output_rows.sort(key=lambda x: x['revenue'], reverse=True)
    
    md = "PRODUCT SALES REPORT (Consolidated):\n"
    md += "| Product Name | Units Sold (Qty) | Total Revenue |\n"
    md += "| :--- | :--- | :--- |\n"
    for row in output_rows:
        md += f"| {row['name']} | {row['count']} | {row['revenue']:,} |\n"
    return md

@mcp.tool()
def fetch_visit_plans_by_clinic() -> str:
    """
    Retrieves 'Planned Visits' grouped by Clinic, distinguishing branches by City.
    """
    city_buckets = helpers.load_clinic_directory()
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
            match = helpers.get_fuzzy_match(core_name, potential_matches, threshold=0.88)
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
    md = "PLANNED VISITS REPORT (Grouped by Clinic):\n"
    md += "| Clinic ID(s) | Clinic Name | Clinic Address | Number of Visits |\n"
    md += "| :--- | :--- | :--- | :--- |\n"
    for row in final_output:
        md += f"| {row['ids']} | {row['name']} | {row['city']} | {row['count']} |\n"
    return md

@mcp.tool()
def fetch_report_counts_by_salesman() -> str:
    """
    Retrieves the count of *Completed* Visits (Reports) grouped by Salesman.
    """
    id_map, _, _, _ = helpers.load_official_users_map()
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
    md = "COMPLETED REPORTS BY SALESMAN:\n"
    md += "| Sales User ID | Salesman Name | Total Reports |\n"
    md += "| :--- | :--- | :--- |\n"
    for row in output_rows:
        md += f"| {row['user_id']} | {row['name']} | {row['count']} |\n"
    return md

@mcp.tool()
def fetch_comprehensive_salesman_performance() -> str:
    """
    Retrieves a 360-degree 'Scorecard' for Salesmen (Plans vs Visits vs Sales).
    """
    id_map, code_map, digit_map, name_list = helpers.load_official_users_map()
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
                resolved_id = helpers.resolve_salesman_identity(part, code_map, digit_map, name_list)
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
            "ratio_pv": ratio_pv, "ratio_vt": ratio_vt
        })

    output_rows.sort(key=lambda x: x['transactions'], reverse=True)
    md = "SALESMAN PERFORMANCE SCORECARD (360 View):\n"
    md += "| Sales User ID | Salesman Name | Total Plans | Total Visits | Total Transactions | Plan to Visit Ratio | Visit to Transaction Ratio |\n"
    md += "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
    for row in output_rows:
        md += f"| {row['code']} | {row['name']} | {row['plans']} | {row['reports']} | {row['transactions']} | {row['ratio_pv']:.2f} | {row['ratio_vt']:.2f} |\n"
    return md

@mcp.tool()
def fetch_salesman_visit_history(salesman_name: str) -> str:
    """
    Fetches detailed visit notes and transaction stats for a SPECIFIC salesman.

    Description:
        Used for deep-dive analysis of a single salesman's performance.
        1. Identifies the salesman ID from the input name.
        2. Fetches their total transaction count (using identity resolution).
        3. Fetches their recent 'visitnote' entries from the reports table.
    
    Parameters:
        salesman_name (str): The name or code of the salesman (e.g., "Wilson", "PS100").

    Returns:
        str: A text log containing stats and a list of visit notes.

    When to use:
        Use when the user asks "Why are [Name]'s sales low?", "Analyze [Name]'s visits", 
        or "Check the effectiveness of [Name]".
    """
    return helpers.fetch_single_salesman_data(salesman_name)

@mcp.tool()
def fetch_salesman_comparison_data(salesman_a: str, salesman_b: str) -> str:
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
        str: A combined text log with two distinct sections (one for each salesman).

    When to use:
        Use when the user asks to "compare Wilson and Gladys", "who is better between A and B",
        or "compare visit effectiveness of A vs B".
    """
    report_a = helpers.fetch_single_salesman_data(salesman_a)
    report_b = helpers.fetch_single_salesman_data(salesman_b)
    
    return f"COMPARISON DATASET:\n\n{report_a}\n\n{report_b}"