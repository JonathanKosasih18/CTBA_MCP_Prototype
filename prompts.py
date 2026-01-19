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