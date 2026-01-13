import os
import sys
import json
# Ensure we can import from agents
# Add the project root (one level up from tests) to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from smart_task_app.tools.notion import query_database, add_task_to_database, get_database_schema

def test_notion_integration():
    print("=== Testing Notion Integration ===")
    
    # 1. Test Schema Retrieval
    print("\n[1] Testing Schema Retrieval...")
    schema = get_database_schema("Task")
    print(f"Schema: {schema}")
    assert "Task" in schema
    
    # 2. Test Adding a Task
    print("\n[2] Testing Add Task...")
    task_title = "Test Task from Integration Script"
    task_id = add_task_to_database(title=task_title)
    print(f"Created Task ID: {task_id}")
    
    if "Error" in task_id:
        print("FAILED: Could not create task.")
        return

    # 3. Test Querying Task
    print("\n[3] Testing Query Task...")
    # Wait a moment for consistency? Usually not needed for immediate read-after-write in Notion API but good practice.
    import time
    time.sleep(2)
    
    results_json = query_database("SELECT * FROM Task")
    results = json.loads(results_json)
    
    found = False
    for task in results:
        if task.get("title") == task_title:
            found = True
            print(f"FOUND: {task}")
            break
            
    if found:
        print("\nSUCCESS: Task created and retrieved successfully!")
    else:
        print("\nWARNING: Task created but not found in recent query results.")
        print(f"Recent results: {results}")

    # 4. Test Querying Project (Read-only check)
    print("\n[4] Testing Query Project...")
    project_results_json = query_database("SELECT * FROM Project")
    project_results = json.loads(project_results_json)
    print(f"Project Results (First 2): {project_results[:2]}")

if __name__ == "__main__":
    test_notion_integration()
