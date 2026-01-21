import re
import datetime
import pytz
from typing import Optional
from collections import defaultdict
from sqlalchemy import text
from server_instance import mcp
from database import engine
import helpers

# --- MCP TOOLS ---

@mcp.tool()
def fetch_deduplicated_visit_report() -> str:
    """
    Retrieves a consolidated report of 'Planned Visits' grouped by standardized Customer ID (CID).
    """
    # 1. Get Visit Counts by Internal ID (customers.id)
    visit_counts = defaultdict(int)
    query_plans = text("SELECT custcode, COUNT(*) as c FROM plans GROUP BY custcode")
    with engine.connect() as conn:
        for row in conn.execute(query_plans):
            visit_counts[str(row.custcode)] = row.c

    # 2. Get Internal ID to Name Map
    internal_customers = []
    query_cust = text("SELECT id, custname FROM customers")
    with engine.connect() as conn:
        for row in conn.execute(query_cust):
            internal_customers.append({
                "id": str(row.id),
                "clean": helpers.normalize_name(row.custname)
            })

    # 3. Get Name to CID Map (Bridging the gap)
    name_to_cid_map = helpers.load_name_to_cid_map()
    available_cid_names = list(name_to_cid_map.keys())

    # 4. Aggregate by CID
    cid_counts = defaultdict(int)

    for cust in internal_customers:
        internal_id = cust['id']
        clean_name = cust['clean']
        count = visit_counts.get(internal_id, 0)
        
        if count == 0 or not clean_name: 
            continue

        # Try exact match first
        found_cid = name_to_cid_map.get(clean_name)

        # If no exact match, try fuzzy match
        if not found_cid:
            match = helpers.get_fuzzy_match(clean_name, available_cid_names, threshold=0.88)
            if match:
                found_cid = name_to_cid_map[match]
        
        # Aggregate
        if found_cid:
            cid_counts[found_cid] += count
        else:
            # Fallback if we absolutely cannot find a CID
            cid_counts[f"[No CID] {internal_id}"] += count

    # 5. Format Output (2 Columns Only)
    final_rows = [{"id": k, "count": v} for k, v in cid_counts.items()]
    final_rows.sort(key=lambda x: x['count'], reverse=True)

    md = "PLANNED VISITS REPORT (By Customer ID):\n"
    md += "| Customer ID | Visit Count |\n"
    md += "| :--- | :--- |\n"
    for row in final_rows:
        md += f"| {row['id']} | {row['count']} |\n"
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
    Retrieves transaction counts grouped by standardized Customer ID (CID).
    """
    # 1. Fetch Raw Data
    query = text("SELECT cust_id, COUNT(*) as c FROM transactions WHERE cust_id IS NOT NULL AND cust_id != '' GROUP BY cust_id")
    
    cid_counts = defaultdict(int)
    
    with engine.connect() as conn:
        for row in conn.execute(query):
            raw_cid = str(row.cust_id)
            count = row.c
            
            # 2. Standardize ID (Convert 'B-CID123' -> 'CID123')
            std_cid = helpers.standardize_customer_id(raw_cid)
            
            # 3. Aggregate
            cid_counts[std_cid] += count

    # 4. Format Output (2 Columns Only)
    output_rows = [{"id": k, "count": v} for k, v in cid_counts.items()]
    output_rows.sort(key=lambda x: x['count'], reverse=True)
    
    md = "TRANSACTION REPORT (By Customer ID):\n"
    md += "| Customer ID | Transaction Count |\n"
    md += "| :--- | :--- |\n"
    for row in output_rows:
        md += f"| {row['id']} | {row['count']} |\n"
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

@mcp.tool()
def fetch_best_performers(start_date: str, end_date: str) -> str:
    """
    Fetches a leaderboard of best performing salesmen and products within a date range or overall.
    
    Description:
        Identifies the top performers across four categories:
        1. Visit Volume (Most visits completed).
        2. Transaction Volume (Most sales transactions).
        3. Revenue Generation (Highest total sales value).
        4. Conversion Efficiency (Highest ratio of Transactions to Visits).
        Also identifies the single most sold product by quantity.
    
    Parameters:
        start_date (str, optional): Start date (YYYY-MM-DD). Defaults to '2015-01-01' if not provided.
        end_date (str, optional): End date (YYYY-MM-DD). Defaults to today (GMT+7) if not provided.

    Returns:
        str: A Markdown formatted leaderboard summary.

    When to use:
        Use when the user asks "Who is the best salesman?", "Show me the top performers for January",
        or "Who had the highest conversion rate last year?".
    """

    # --- DEFAULT DATE LOGIC ---
    # Apply Defaults if arguments are missing or empty strings
    tz = pytz.timezone('Asia/Jakarta')
    today = datetime.datetime.now(tz).strftime('%Y-%m-%d')
    final_start = start_date if start_date and start_date.strip() else '2015-01-01'
    final_end = end_date if end_date and end_date.strip() else today
    return helpers.fetch_best_performers_logic(final_start, final_end)