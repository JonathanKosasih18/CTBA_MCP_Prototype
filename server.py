from fastapi import FastAPI
import uvicorn

# Import the server instance
from server_instance import mcp

# Import tools and prompts to register them with the server
import tools
import prompts

# Initialize FastAPI app
app = FastAPI(title="CTBA Analytics Server")

# --- Define API endpoints ---
@app.get("/api/health")
def health_check():
    return {"status": "online", "database": "connected"}

# Mount the MCP SSE app
app.mount("/mcp", mcp.sse_app())

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)