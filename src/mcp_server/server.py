import os
import threading
from mcp.server.fastmcp import FastMCP

from src.task_management.tools import register_tools
from src.task_execution.scheduler import scheduler_daemon
from src.resource_management.supervisor import agent_supervisor
import logging

logger = logging.getLogger("smart_task.mcp_server")
logging.basicConfig(level=logging.INFO)

# Initialize FastMCP Server
mcp = FastMCP("Smart Task Hub")

# Fix: Disable DNS rebinding protection for Docker internal networking
mcp.settings.transport_security.enable_dns_rebinding_protection = False

# Register all Database CRUD and context tools
register_tools(mcp)

if __name__ == "__main__":
    import argparse
    import asyncio
    
    # Start the execution scheduler strictly in the background
    threading.Thread(target=scheduler_daemon, daemon=True).start()

    # Bootstrap the persistent agent pool (API servers) 
    # Only if NOT explicitly disabled via env var (e.g. in Docker Compose)
    if os.getenv("DOCKER_MANAGED_AGENTS", "false").lower() != "true":
        agent_supervisor.bootstrap()
    else:
        logger.info("Agents are managed by Docker. Skipping local bootstrap.")
        agent_supervisor.load_config()

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
        print(f"Starting Streamable HTTP MCP server on http://0.0.0.0:{args.port}/mcp")
        # Run HTTP streamable server
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = args.port
        # mcp.run correctly executes uvicorn binding 
        mcp.run(transport="streamable-http")
    else:
        # Use Standard IO (for local test setups in Cursor / Claude Code)
        mcp.run(transport="stdio")
