from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Optional
import uvicorn
import contextlib

# Import the server instance
from server_instance import mcp

# Import tools and prompts to register them with the server
import tools
import prompts

# Lifecycle Manager (Optional but good practice)
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic here if needed
    print("--- CTBA Analytics Server Starting ---")
    yield
    # Shutdown logic here
    print("--- Server Shutting Down ---")

# Initialize FastAPI app
app = FastAPI(
    title="CTBA Analytics Server",
    description="Hybrid Server: Serves both MCP Protocol and REST API",
    version="1.0.0",
    lifespan=lifespan
)

# Mount MCP Server through SSE
app.mount("/mcp", mcp.sse_app())

# API Endpoints
@app.get("/")
async def root():
    return {"message": "CTBA MCP Server is running. Access MCP at /mcp/sse"}

@app.get("/api/visits/customers")
def get_visits_by_customer():
    return tools.fetch_deduplicated_visit_report()

@app.get("/api/visits/salesmen")
def get_visits_by_salesman():
    return tools.fetch_visit_plans_by_salesman()

@app.get("/api/visits/clinics")
def get_visits_by_clinic():
    return tools.fetch_visit_plans_by_clinic()

@app.get("/api/transactions/customers")
def get_transactions_by_customer():
    return tools.fetch_transaction_report_by_customer_name()

@app.get("/api/transactions/salesmen")
def get_transactions_by_salesman():
    return tools.fetch_deduplicated_sales_report()

@app.get("/api/transactions/products")
def get_transactions_by_product():
    return tools.fetch_transaction_report_by_product()

@app.get("/api/reports/salesmen")
def get_reports_by_salesman():
    return tools.fetch_report_counts_by_salesman()

@app.get("/api/performance/salesmen")
def get_salesman_performance_scorecard():
    return tools.fetch_comprehensive_salesman_performance()

@app.get("/api/analysis/salesman/{name}")
def analyze_salesman_effectiveness(name: str):
    return tools.fetch_salesman_visit_history(name)

@app.get("/api/analysis/compare")
def compare_salesmen(salesman_a: str, salesman_b: str):
    return tools.fetch_salesman_comparison_data(salesman_a, salesman_b)

@app.get("/api/performance/best")
def get_best_performers(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    # Default is output_format=0, so this returns pure JSON
    return tools.fetch_best_performers(start_date, end_date)

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)