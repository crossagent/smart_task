import os
import threading
from mcp.server.fastmcp import FastMCP

from src.task_management.tools import register_tools
from src.task_execution.scheduler import scheduler_daemon

# Initialize FastMCP Server
mcp = FastMCP("Smart Task Hub")

# Register all Database CRUD and context tools
register_tools(mcp)

if __name__ == "__main__":
    import argparse
    import asyncio
    
    # Start the execution scheduler strictly in the background
    threading.Thread(target=scheduler_daemon, daemon=True).start()

    # Allow transport selection via environment variable or command line
    default_transport = os.getenv("MCP_TRANSPORT", "stdio")
    default_port = int(os.getenv("PORT", "45666"))
    
    parser = argparse.ArgumentParser(description="Run the Smart Task Hub MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=default_transport,
                        help="Transport protocol to use (stdio by default)")
    parser.add_argument("--port", type=int, default=default_port,
                        help="Port for the HTTP server (if using http transport)")
    args = parser.parse_args()

    if args.transport == "http":
        print(f"Starting MCP server on http://0.0.0.0:{args.port}/sse")
        # Run SSE server manually using asyncio
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = args.port
        # mcp.run correctly executes uvicorn binding 
        mcp.run(transport="sse")
    else:
        # Use Standard IO (for local test setups in Cursor / Claude Code)
        mcp.run(transport="stdio")
