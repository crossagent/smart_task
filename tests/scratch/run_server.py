from __future__ import annotations
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

# Force UTF-8 encoding for Windows console
os.environ["PYTHONUTF8"] = "1"

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9011
    print(f"Starting A2A server on port {port}...")
    try:
        app = get_fast_api_app(
            agents_dir="smart_task_app/agents",
            a2a=True,
            port=port,
            web=False
        )
        print(f"FastAPI app created for port {port}. Starting uvicorn...")
        uvicorn.run(app, host="127.0.0.1", port=port)
    except Exception as e:
        print(f"Error starting server on port {port}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
