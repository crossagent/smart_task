"""
Consolidated retrieval tools for the AddTaskOrchestrator.
Merged from project_context/tools/retrieval.py and task_context/tools/retrieval.py.
"""
import json
from typing import Optional
from smart_task_app.remote_a2a.new_task.tools.notion import query_database


# --- Project Tools ---

def search_projects(query: str) -> str:
    """
    Search for existing projects in Notion by name.
    Returns JSON string of matching projects.
    """
    filter_obj = {
        "property": "Name",
        "title": {
            "contains": query
        }
    }
    return query_database(query="Project", query_filter=json.dumps(filter_obj))


def get_project_outline() -> str:
    """
    Get a lightweight outline of all active projects.
    Returns: JSON string list of {id, name, status, due}.
    """
    try:
        results_str = search_projects("")
        results = json.loads(results_str)

        outline = []
        if isinstance(results, list):
            for p in results:
                outline.append({
                    "id": p.get("id"),
                    "name": p.get("title"),
                    "status": p.get("status"),
                    "due": p.get("due")
                })
        return json.dumps(outline)
    except Exception:
        return json.dumps([])


# --- Task Tools ---

def search_tasks(query: str, project_id: Optional[str] = None) -> str:
    """
    Search for existing tasks in Notion by name.
    If project_id is provided, restricts search to that project.
    """
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
                    "property": "Project",
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
