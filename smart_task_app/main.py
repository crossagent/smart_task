"""Smart Task App - Main Entry Point."""

from __future__ import annotations

import os
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from smart_task_app.agent import root_agent

from pathlib import Path
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Create ADK middleware agent instance
# Note: session_timeout_seconds and use_in_memory_services can be adjusted as needed
adk_smart_task_agent = ADKAgent(
    adk_agent=root_agent,
    user_id="demo_user",
    session_timeout_seconds=3600,
    use_in_memory_services=True,
)

# Create FastAPI app
app = FastAPI(title="ADK Smart Task Agent")

# Add the ADK endpoint
add_adk_fastapi_endpoint(app, adk_smart_task_agent, path="/")

def main():
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Warning: GOOGLE_API_KEY environment variable not set!")
        print("   Set it with: export GOOGLE_API_KEY='your-key-here'")
        print("   Get a key from: https://makersuite.google.com/app/apikey")
        print()

    port = int(os.getenv("PORT", 8000))
    # Use 0.0.0.0 to be accessible from other containers/processes if needed, but localhost is fine for local dev
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
