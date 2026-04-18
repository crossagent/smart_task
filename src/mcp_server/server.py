import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from mcp.server.fastmcp import FastMCP

from src.task_management.tools import register_tools
from src.task_execution.scheduler import scheduler_daemon
from src.resource_management.supervisor import agent_supervisor
from .dashboard_api import router as dashboard_router
import logging

logger = logging.getLogger("smart_task.mcp_server")
logging.basicConfig(level=logging.INFO)

# 1. Initialize FastMCP Server
mcp = FastMCP("Smart Task Hub")
mcp.settings.transport_security.enable_dns_rebinding_protection = False
register_tools(mcp)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle hook to start background processes."""
    # Start the execution scheduler in the background
    scheduler_thread = threading.Thread(target=scheduler_daemon, daemon=True)
    scheduler_thread.start()

    # Bootstrap agents if needed
    if os.getenv("DOCKER_MANAGED_AGENTS", "false").lower() != "true":
        agent_supervisor.bootstrap()
    else:
        logger.info("Agents are managed by Docker. Loading config...")
        agent_supervisor.load_config()
    
    yield
    # Cleanup if needed

# 2. Initialize FastAPI App
app = FastAPI(title="Smart Task Hub Dashboard", lifespan=lifespan)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Mount MCP App
# FastMCP provides streamable_http_app() for ASGI integration
app.mount("/mcp", mcp.streamable_http_app())

# 4. Include Dashboard APIs
app.include_router(dashboard_router)

# 5. Serve Static Dashboard at /dashboard
if os.path.exists("dashboard/dist"):
    app.mount("/dashboard", StaticFiles(directory="dashboard/dist", html=True), name="dashboard")
    
    @app.get("/")
    async def root_redirect():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/dashboard")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "45666"))
    uvicorn.run(app, host="0.0.0.0", port=port)
