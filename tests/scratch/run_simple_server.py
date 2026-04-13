from __future__ import annotations
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

def main():
    print("Starting manual A2A server...")
    try:
        app = get_fast_api_app(
            agents_dir="smart_task_app/agents",
            a2a=True,
            port=9013,
            web=False
        )
        print("FastAPI app created. Starting uvicorn...")
        uvicorn.run(app, host="127.0.0.1", port=9013)
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
