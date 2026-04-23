import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp.utilities.lifespan import combine_lifespans
from contextlib import asynccontextmanager

# Simple flat imports
from .mcp_app import mcp
import tools 
from .scheduler import scheduler_daemon
from .supervisor import agent_supervisor
from .dashboard_api import router as dashboard_router
import logging

logger = logging.getLogger("smart_task.mcp_server")
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    """Lifecycle hook to start project-specific background processes."""
    logger.info("Starting up project background tasks...")
    
    scheduler_thread = threading.Thread(target=scheduler_daemon, daemon=True)
    scheduler_thread.start()

    if os.getenv("DOCKER_MANAGED_AGENTS", "false").lower() != "true":
        agent_supervisor.bootstrap()
    else:
        logger.info("Agents are managed by Docker. Loading config...")
        agent_supervisor.load_config()
    
    yield
    logger.info("Shutting down project background tasks...")

mcp_app = mcp.http_app(transport="sse")

app = FastAPI(
    title="Smart Task Hub Dashboard", 
    lifespan=combine_lifespans(app_lifespan, mcp_app.lifespan)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/mcp", mcp_app)
app.include_router(dashboard_router)

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
