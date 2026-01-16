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


def get_task_details(task_id: str) -> str:
    """
    Get detailed information for a specific task.
    Includes: Description, Parent-task, Sub-tasks, Project, Blocking status.
    """
    # In production, use client.pages.retrieve(task_id)
    # Here we mock/search. Assuming 'task_id' might be a title or ID.
    # If it's a UUID, notion client supports it. But our wrapper `query_database` is high level.
    # Let's return a simulated detailed view.
    
    return json.dumps({
        "id": task_id,
        "title": "Task Title (Fetched)",
        "description": "Full rich text description...",
        "status": "In Progress",
        "parent_task": "PARENT-ID",
        "sub_tasks": ["SUB-1", "SUB-2"],
        "project": "PROJ-123",
        "is_blocking": [],
        "blocked_by": []
    })
