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

    3. **Conclusion**:
        - Is this salesman working efficiently?
        - Are they making too many "empty visits" (visits where the doctor isn't there)?
        - Provide 1-2 actionable recommendations based on the notes.
    """

@mcp.prompt()
def compare_salesmen_effectiveness(salesman_a: str, salesman_b: str) -> str:
    """
    Generates a prompt to compare the performance and effectiveness of two salesmen.
    """
    return f"""
    Act as a Senior Sales Manager. I need a comparative analysis between two salesmen: {salesman_a} vs {salesman_b}.
    
    Please run the tool `fetch_salesman_comparison_data` with arguments '{salesman_a}' and '{salesman_b}'.
    
    Once you have the data, perform a side-by-side analysis:
    
    ### 1. Quantitative Comparison (The Numbers)
    - Compare their **Conversion Ratios** (Total Transactions / Total Visits).
    - Who has the higher volume of activity?
    
    ### 2. Qualitative Comparison (The "Why")
    Analyze the `visitnotes` (Bahasa Indonesia) for both.
    - **{salesman_a}**: What are their common obstacles? (e.g., "Dokter cuti", "Stok full")? What are their strengths?
    - **{salesman_b}**: How does their situation differ? Do they meet doctors more often?
    
    ### 3. Verdict & Conclusion
    - Who is the more effective salesman right now?
    - Is the lower-performing salesman lazy (no visits) or just unlucky (doctors unavailable)?
    - Give a specific recommendation for each person.
    """

@mcp.prompt()
def generate_best_performers_report(start_date: str, end_date: str) -> str:
    """
    Generates a prompt for identifying the best performing salesmen and products.
    
    The LLM should:
    1. Parse the user's natural language date request (e.g., "last month", "Q1 2025") into YYYY-MM-DD.
    2. Pass these dates into the tool execution arguments.
    """
    return f"""
    You are an expert Sales Performance Analyst.
    The user wants to know who the "Best Performers" are for the period: {start_date} to {end_date}.

    Step 1: Confirm the date range (YYYY-MM-DD) provided in the arguments.
    Step 2: Call the tool `fetch_best_performers` with these exact dates.
    Step 3: Once you receive the tool output (the leaderboard), present it enthusiastically to the user.
    Step 4: Add a brief 1-sentence observation summarizing the result (e.g., "It seems [Name] is dominating in revenue, but [Name] is more efficient with visits.").
    """