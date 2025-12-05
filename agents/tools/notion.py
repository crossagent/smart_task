import os
import json
from typing import Optional, Dict, Any
from notion_client import Client

# Initialize Notion client if API key is present
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
notion = Client(auth=NOTION_API_KEY) if NOTION_API_KEY else None

def get_database_schema(database_name: str) -> str:
    """
    Returns the schema for a given database table.
    Args:
        database_name: 'Project' or 'Task'
    """
    # In a real implementation, we might query the database to get its properties.
    # For now, we'll return a hardcoded schema that matches our expected structure.
    # This helps the LLM understand what fields are available.
    
    if database_name.lower() == 'project':
        return json.dumps({
            "table": "Project",
            "columns": ["id", "title", "status", "owner", "tasks"],
            "description": "Projects database containing high-level goals."
        })
    if database_name.lower() == 'task':
        return json.dumps({
            "table": "Task",
            "columns": ["id", "title", "status", "due_date", "priority", "project_id"],
            "description": "Tasks database containing actionable items."
        })
    return '{"error": "Database not found"}'

def query_database(query: str) -> str:
    """
    Executes a SQL-like query against the Notion databases.
    Supported syntax: SELECT * FROM [Table] WHERE [Condition]
    Example: "SELECT * FROM Task WHERE status = 'In Progress'"
    """
    if not notion:
        print("[Notion] No API key found. Returning mock data.")
        # Mock implementation for testing without credentials
        if "from task" in query.lower() and "in progress" in query.lower():
            return json.dumps([
                {"id": "t1", "title": "Refactor Agents", "status": "In Progress", "priority": "High", "due_date": "2025-12-06"},
                {"id": "t2", "title": "Write Documentation", "status": "In Progress", "priority": "Medium", "due_date": "2025-12-07"}
            ])
        return '[]'

    # TODO: Implement actual SQL-to-Notion-Filter parsing
    # This is a complex task. For this "run through", we will implement a simple
    # keyword matching to demonstrate the concept.
    
    try:
        # Simplified logic: If query mentions "Task", query the Task database
        # Note: You would need the actual Database ID here.
        # For now, we'll just print what we would do.
        print(f"[Notion] Executing query: {query}")
        return json.dumps({"message": "Query executed (simulated)", "query": query})
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def add_task_to_database(title: str, status: str = "Not Started", priority: str = "Medium", due_date: Optional[str] = None) -> str:
    """
    Adds a new task to the Notion 'Task' database.
    Args:
        title: Task title
        status: Task status
        priority: Task priority
        due_date: Due date (YYYY-MM-DD)
    Returns:
        The ID of the created task.
    """
    if not notion:
        print(f"[Notion] No API key. Mock creating task: {title}")
        return "new_task_id_mock"

    try:
        # TODO: Replace with actual Database ID
        # database_id = "YOUR_DATABASE_ID" 
        
        print(f"[Notion] Creating task in Notion: {title}")
        # response = notion.pages.create(...)
        return "new_task_id_real"
    except Exception as e:
        return f"Error creating task: {str(e)}"
