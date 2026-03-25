import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from smart_task_app.scheduling_assistant.tool import fetch_workload_and_resources, apply_scheduling_results

async def test_fetch_tools():
    print("Testing fetch_workload_and_resources...")
    try:
        result = await fetch_workload_and_resources(tool_context=None)
        print("Fetch Result Summary:")
        print(result[:500] + "..." if len(result) > 500 else result)
        assert "BACKLOG" in result or "No pending tasks found" in result
        print("Fetch tool works correctly.")
    except Exception as e:
        print(f"Fetch tool failed: {e}")
        import traceback
        traceback.print_exc()

async def test_apply_tools():
    # We won't actually commit unless we have a real task ID to test with safely.
    # But we can verify the function signature and basic logic.
    print("\nTesting apply_scheduling_results (Dry Run / Validation)...")
    try:
        # Pass dummy data that should fail validation or be recognized as empty
        result = await apply_scheduling_results(scheduling_results=[], tool_context=None)
        print(f"Apply Result: {result}")
        assert "No scheduling results provided" in result
        print("Apply tool validation works.")
    except Exception as e:
        print(f"Apply tool failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_fetch_tools())
    asyncio.run(test_apply_tools())
