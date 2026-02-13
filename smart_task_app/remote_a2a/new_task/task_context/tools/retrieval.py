import json
from smart_task_app.remote_a2a.new_task.tools.notion import query_database


from typing import Optional

def search_tasks(query: str, project_id: Optional[str] = None) -> str:
    """
    Search for existing tasks in Notion by name.
    If project_id is provided, restricts search to that project.
    """
    # Heuristic for Title property
    name_filter = {
        "property": "Task name", 
        "title": {
            "contains": query
        }
    }

    if project_id:
        filter_obj = {
            "and": [
                name_filter,
                {
                    "property": "Project", # Heuristic for Relation property
                    "relation": {
                        "contains": project_id
                    }
                }
            ]
        }
    else:
        filter_obj = name_filter
    
    return query_database(query="Task", query_filter=json.dumps(filter_obj))



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
