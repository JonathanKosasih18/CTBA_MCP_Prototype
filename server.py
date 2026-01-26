from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse
from typing import Optional
import uvicorn
import contextlib

# Import the server instance
from server_instance import mcp

# This registers the tools with the 'mcp' object
import tools
import prompts

# Lifecycle Manager
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- CTBA Analytics Server Starting ---")
    yield
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

@app.get("/visits/customers")
def get_visits_by_customer():
    return tools.fetch_deduplicated_visit_report()

@app.get("/visits/salesmen")
def get_visits_by_salesman():
    return tools.fetch_visit_plans_by_salesman()

@app.get("/visits/clinics")
def get_visits_by_clinic():
    return tools.fetch_visit_plans_by_clinic()

@app.get("/transactions/customers")
def get_transactions_by_customer():
    return tools.fetch_transaction_report_by_customer_name()

@app.get("/transactions/salesmen")
def get_transactions_by_salesman():
    return tools.fetch_deduplicated_sales_report()

@app.get("/transactions/products")
def get_transactions_by_product():
    return tools.fetch_transaction_report_by_product()

@app.get("/reports/salesmen")
def get_reports_by_salesman():
    return tools.fetch_report_counts_by_salesman()

@app.get("/performance/salesmen")
def get_salesman_performance_scorecard():
    return tools.fetch_comprehensive_salesman_performance()

@app.get("/analysis/salesman/{name}")
def analyze_salesman_effectiveness(name: str):
    return tools.fetch_salesman_visit_history(name)

@app.get("/analysis/compare")
def compare_salesmen(salesman_a: str, salesman_b: str):
    return tools.fetch_salesman_comparison_data(salesman_a, salesman_b)

@app.get("/performance/best")
def get_best_performers(
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD")
):
    # Default is output_format=0, so this returns pure JSON
    return tools.fetch_best_performers(start_date, end_date)

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

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)