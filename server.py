from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
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

# Run the MCP server
if __name__ == "__main__":
    print("Starting CTBA MCP Server...")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)