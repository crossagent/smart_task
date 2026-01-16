import json
from smart_task_app.new_task.tools.notion import query_database

def search_tasks(query: str) -> str:
    """
    Search for existing tasks in Notion by name.
    Useful for checking duplication or finding parent tasks.
    """
    # Heuristic: assume 'Name' or 'Task name' property
    filter_obj = {
        "property": "Task name", # This might need adjustment based on Schema
        "title": {
            "contains": query
        }
    }
    # Fallback if property name is wrong in heuristic: try "Name"
    # Ideally we use SCHEMA but for now let's try one.
    
    return query_database(query="Task", query_filter=json.dumps(filter_obj))

def check_duplication(task_title: str) -> str:
    """
    Check if a task with similar title exists.
    Returns "DUPLICATE_FOUND: [details]" or "NO_DUPLICATE".
    """
    result = search_tasks(task_title)
    try:
        data = json.loads(result)
        if data and isinstance(data, list) and len(data) > 0:
            return f"DUPLICATE_FOUND: Found {len(data)} similar tasks. First: {data[0].get('title')}"
        return "NO_DUPLICATE"
    except:
        return "ERROR_CHECKING_DUPLICATION"
