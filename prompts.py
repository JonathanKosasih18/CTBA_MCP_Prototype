from server_instance import mcp

@mcp.prompt()
def generate_planned_visits_report_by_customer() -> str:
    """Generates a prompt to request the planned visits report grouped by customer."""
    return """
    I need a Planned Visits Report grouped by Customer.
    Please run the tool `fetch_deduplicated_visit_report`.
    Output the result exactly as the tool returns it (Markdown Table).
    """

@mcp.prompt()
def generate_planned_visits_report_by_salesman() -> str:
    """Generates a prompt to request the planned visits report grouped by salesman."""
    return """
    I need a Planned Visits Report grouped by Salesman.
    Please run the tool `fetch_visit_plans_by_salesman`.
    Output the table exactly as returned by the tool.
    """

@mcp.prompt()
def generate_planned_visits_report_by_clinic() -> str:
    """Generates a prompt to request the planned visits report grouped by clinic."""
    return """
    I need a Planned Visits Report grouped by Clinic.
    Please run the tool `fetch_visit_plans_by_clinic`.
    The output will be a table with columns: 
    | Clinic ID(s) | Clinic Name | Clinic Address | Number of Visits |
    """

@mcp.prompt()
def generate_transaction_report_by_salesmen() -> str:
    """Generates a prompt to request the consolidated sales report."""
    return """
    I need the Sales Performance Report.
    Please run the tool `fetch_deduplicated_sales_report`.
    Display the returned table exactly as is.
    """

@mcp.prompt()
def generate_transaction_report_by_customer() -> str:
    """Generates a prompt to request the customer transaction report."""
    return """
    I need the Transaction Report grouped by Customer Name.
    Please run the tool `fetch_transaction_report_by_customer_name`.
    """

@mcp.prompt()
def generate_transaction_report_by_product() -> str:
    """Generates a prompt to request the product sales report."""
    return """
    I need the Transaction Report grouped by Product.
    Please run the tool `fetch_transaction_report_by_product`.
    """

@mcp.prompt()
def generate_report_counts_by_salesman() -> str:
    """Generates a prompt to request the count of completed visit reports grouped by salesman."""
    return """
    I need a Report on Completed Visits (Reports) grouped by Salesman.
    Please run the tool `fetch_report_counts_by_salesman`.
    Output the table exactly as returned by the tool.
    """

@mcp.prompt()
def generate_comprehensive_salesman_report() -> str:
    """Generates a prompt for the all-in-one Salesman Performance Scorecard."""
    return """
    I need the Comprehensive Salesman Performance Report (Scorecard).
    Please run the tool `fetch_comprehensive_salesman_performance`.
    Display the result exactly as returned.
    """

@mcp.prompt()
def analyze_salesman_visit_effectiveness(salesman_name: str) -> str:
    """
    Generates a prompt to analyze WHY a specific salesman is performing well or poorly.
    """
    return f"""
    Act as a Sales Performance Analyst. I need you to evaluate the effectiveness of salesman: {salesman_name}.
    
    Please run the tool `fetch_salesman_visit_history` with the argument '{salesman_name}'.
    
    Once you have the data, perform the following analysis:
    
    1. **Calculate the Conversion Ratio**: (Total Transactions / Total Visits).
    
    2. **Analyze the Visit Notes (Bahasa Indonesia)**:
        Read the visit notes and categorize them to explain the ratio. Look for patterns such as:
        - **Availability Issues**: "Dokter tidak ada", "Tutup", "Cuti", "Seminar".
        - **Stock Issues**: "Stok masih ada", "Barang numpuk", "Belum perlu".
        - **Competitor Issues**: "Pakai produk lain", "Harga kompetitor lebih murah".
        - **Positive Signals**: "Minta invoice", "Order", "Tertarik".

    3. **Strengths & Weaknesses (Strong and Weak Points)**:
        - List the salesman's key strengths (skills, behaviors, recurring positive patterns) with concrete examples from visit notes and metrics.
        - List the salesman's main weaknesses (gaps, recurring negative patterns, process issues) with evidence from notes and data.
        - For each point, provide a short justification (1-2 sentences) linking to specific notes or numeric indicators.

    4. **Conclusion**:
        - Is this salesman working efficiently?
        - Are they making too many "empty visits" (visits where the doctor isn't there)?
        - Provide 1-2 actionable recommendations based on the notes.
    """

@mcp.prompt()
def compare_salesmen_effectiveness(salesman_a: str, salesman_b: str) -> str:
    """
    Generates a prompt to compare the performance and effectiveness of two salesmen,
    including each salesman's strengths and weaknesses with evidence and short justifications.
    """
    return f"""
    Act as a Senior Sales Manager. I need a clear comparative analysis between two salesmen: {salesman_a} vs {salesman_b}.
    
    Please run the tool `fetch_salesman_comparison_data` with arguments '{salesman_a}' and '{salesman_b}'.
    
    After retrieving data, produce the following sections:

    1. QUANTITATIVE COMPARISON
    - Conversion Ratio (Total Transactions / Total Visits) for each.
    - Total Visits and Total Transactions for each.
    - Who has higher activity volume and by how much (absolute and %).

    2. VISIT NOTES ANALYSIS (Bahasa Indonesia)
    - Summarize the top 3 recurring themes/phrases in visit notes for {salesman_a}.
    - Summarize the top 3 recurring themes/phrases in visit notes for {salesman_b}.

    3. STRENGTHS & WEAKNESSES (for EACH salesman)
    For {salesman_a}:
    - Strengths: List 3 (or up to 3) strengths. For each, give a 1-2 sentence justification citing specific notes or numeric evidence.
    - Weaknesses: List 3 (or up to 3) weaknesses. For each, give a 1-2 sentence justification citing specific notes or numeric evidence.

    For {salesman_b}:
    - Strengths: List 3 (or up to 3) strengths. For each, give a 1-2 sentence justification citing specific notes or numeric evidence.
    - Weaknesses: List 3 (or up to 3) weaknesses. For each, give a 1-2 sentence justification citing specific notes or numeric evidence.

    4. SIDE-BY-SIDE SUMMARY TABLE
    - Provide a concise table or bullet list comparing key metrics and the top 2 strengths & weaknesses side-by-side.

    5. VERDICT & ACTIONABLE RECOMMENDATIONS
    - Who is more effective right now and why (data + notes)?
    - Is the lower-performing salesman lazy (low visits) or unlucky (doctor unavailability, stock issues)?
    - Provide 1 specific, prioritized recommendation for {salesman_a} and 1 for {salesman_b} to improve performance.

    Ensure all claims reference specific metrics or visit note excerpts (in Bahasa Indonesia) as evidence.
    """

@mcp.prompt()
def generate_best_performers_report() -> str:
    """
    Generates a prompt for identifying the best performing salesmen and products.
    
    The LLM should:
    1. Parse the user's natural language date request (e.g., "last month", "Q1 2025") into YYYY-MM-DD.
    2. Pass these dates into the tool execution arguments.
    """
    return f"""
    You are an expert Sales Performance Analyst. 
    The user wants to see the "Best Performers" leaderboard.
    
    ### INSTRUCTIONS:
    1. **Analyze the User's Request** to find a date range (e.g., "last month", "October 2025", "2023").
    2. **Determine the Dates** (YYYY-MM-DD):
        - If a specific range is mentioned, calculate the start and end dates.
        - If NO date is mentioned (e.g., "Show me best performers"), use the **All Time** defaults:
            - Start: '2015-01-01'
            - End: [Current Date in YYYY-MM-DD]
    3. **Call the Tool**: `fetch_best_performers(start_date=..., end_date=...)`.
    4. **Present the Result**: detailed and enthusiastic.
    """