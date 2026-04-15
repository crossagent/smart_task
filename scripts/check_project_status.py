import json
from src.task_management.db import execute_query, CustomEncoder
from src.task_management.tools import get_activity_schedule_report

def check_status():
    print("--- Searching for Latest Activity ---")
    query = "SELECT id, name, created_at FROM activities ORDER BY created_at DESC LIMIT 5"
    results = execute_query(query)
    if not results:
        print("No activities found.")
        return

    print(json.dumps(results, indent=2, cls=CustomEncoder, ensure_ascii=False))
    
    latest_id = results[0]['id']
    print(f"\n--- Generating Report for {latest_id} ---")
    report = get_activity_schedule_report(latest_id)
    print(report)

if __name__ == "__main__":
    check_status()
