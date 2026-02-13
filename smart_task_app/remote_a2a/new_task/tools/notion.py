import os
import json
from typing import Optional, Dict, Any, List
from notion_client import Client
from dotenv import load_dotenv

# Load env vars from root .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), '.env'))

# Initialize Notion client
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_PROJECT_DATABASE_ID = os.environ.get("NOTION_PROJECT_DATABASE_ID")
NOTION_TASK_DATABASE_ID = os.environ.get("NOTION_TASK_DATABASE_ID")

# Global cache for data source ID
_DATA_SOURCE_ID_CACHE = {}

# Load schema
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'notion_schema.json')
NOTION_SCHEMA = {}
if os.path.exists(SCHEMA_PATH):
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            NOTION_SCHEMA = json.load(f)
    except Exception as e:
        print(f"Error loading Notion schema: {e}")

def _get_notion_client() -> Optional[Client]:
    if not NOTION_API_KEY:
        return None
    return Client(auth=NOTION_API_KEY, notion_version="2025-09-03")

def _get_data_source_id(client: Client, database_id: str) -> Optional[str]:
    global _DATA_SOURCE_ID_CACHE
    if database_id in _DATA_SOURCE_ID_CACHE:
        return _DATA_SOURCE_ID_CACHE[database_id]

    try:
        response = client.databases.retrieve(database_id=database_id)
        data_sources = response.get("data_sources", [])
        if data_sources:
            ds_id = data_sources[0]["id"]
            _DATA_SOURCE_ID_CACHE[database_id] = ds_id
            return ds_id
        else:
            print(f"[Notion] No data sources found for database {database_id}")
            return None
    except Exception as e:
        print(f"[Notion] Error retrieving database {database_id}: {e}")
        return None

def _find_property_name_by_type(schema, prop_type):
    for name, info in schema.items():
        if info["type"] == prop_type:
            return name
    return None

def query_database(query: str, query_filter: Optional[str] = None) -> str:
    """
    Executes a query against the Notion databases.
    query: 'Project' or 'Task' to select DB.
    """
    client = _get_notion_client()
    if not client:
        return json.dumps({"error": "Notion API key not configured."})

    database_id = None
    q_lower = query.lower() if query else ""
    
    if "project" in q_lower:
        database_id = NOTION_PROJECT_DATABASE_ID
    elif "task" in q_lower:
        database_id = NOTION_TASK_DATABASE_ID
    else:
        database_id = NOTION_TASK_DATABASE_ID
    
    if not database_id:
        return json.dumps({"error": "Database ID not found."})

    data_source_id = _get_data_source_id(client, database_id)
    if not data_source_id:
        return json.dumps({"error": "Could not resolve Data Source ID."})

    try:
        body = {"page_size": 10}
        
        if query_filter:
            try:
                if isinstance(query_filter, str):
                    filter_obj = json.loads(query_filter)
                else:
                    filter_obj = query_filter
                if filter_obj:
                    body["filter"] = filter_obj
            except json.JSONDecodeError:
                return json.dumps({"error": "Invalid JSON in query_filter."})

        response = client.request(
            method="POST",
            path=f"data_sources/{data_source_id}/query",
            body=body
        )
        
        results = response.get("results", [])
        simplified_results = []
        for page in results:
            props = page.get("properties", {})
            item = {"id": page["id"]}
            for key, value in props.items():
                if value["type"] == "title":
                    item["title"] = value["title"][0]["text"]["content"] if value["title"] else ""
                elif value["type"] == "select":
                    item[key.lower()] = value["select"]["name"] if value["select"] else None
                elif value["type"] == "status":
                    item[key.lower()] = value["status"]["name"] if value["status"] else None
                elif value["type"] == "date":
                    item[key.lower()] = value["date"]["start"] if value["date"] else None
            
            simplified_results.append(item)
            
        return json.dumps(simplified_results, indent=2)
        
    except Exception as e:
        return json.dumps({"error": str(e)})

def add_project_to_database(title: str, goal: str = "", status: str = "Planning", due_date: Optional[str] = None) -> str:
    client = _get_notion_client()
    if not client or not NOTION_PROJECT_DATABASE_ID:
        return "Error: Notion Config missing."

    data_source_id = _get_data_source_id(client, NOTION_PROJECT_DATABASE_ID)
    if not data_source_id:
        return "Error: Project Data Source ID missing."

    try:
        properties = {
            "Name": {"title": [{"text": {"content": title}}]},
            "Status": {"status": {"name": status}},
        }
        if goal:
            # Assuming 'Goal' is a text field or we append to description. 
            # For now, let's assume there is a rich_text property 'Goal'
            properties["Goal"] = {"rich_text": [{"text": {"content": goal}}]}
        
        if due_date:
            properties["Due Date"] = {"date": {"start": due_date}}

        response = client.pages.create(
            parent={"database_id": NOTION_PROJECT_DATABASE_ID},
            properties=properties
        )
        return response["id"]
    except Exception as e:
        return f"Error creating project: {str(e)}"

def add_task_to_database(
    title: str, 
    status: str = "Not Started", 
    priority: str = "Medium", 
    due_date: Optional[str] = None,
    parent_project_id: Optional[str] = None,
    parent_task_id: Optional[str] = None
) -> str:
    """
    Adds a task or subtask.
    If parent_task_id is provided, it's a subtask (conceptually), but stored in Task DB.
    """
    client = _get_notion_client()
    if not client or not NOTION_TASK_DATABASE_ID:
        return "Error: Notion Config missing."
    
    data_source_id = _get_data_source_id(client, NOTION_TASK_DATABASE_ID)
    if not data_source_id:
        return "Error: Task Data Source ID missing."

    task_schema = NOTION_SCHEMA.get("Task", {})
    
    # Heuristic property mapping
    title_prop = "Task name" if "Task name" in task_schema else "Name"
    status_prop = "Status"
    priority_prop = "Priority"
    due_prop = "Due Date" if "Due Date" in task_schema else "Due"
    project_rel_prop = "Project" # Relation to Project DB
    parent_task_prop = "Parent Task" # Relation to Task DB (recursive)

    try:
        properties = {
            title_prop: {"title": [{"text": {"content": title}}]},
        }
        if status:
            properties[status_prop] = {"status": {"name": status}}
        if priority:
            properties[priority_prop] = {"select": {"name": priority}}
        if due_date:
            properties[due_prop] = {"date": {"start": due_date}}
        
        if parent_project_id:
            properties[project_rel_prop] = {"relation": [{"id": parent_project_id}]}
            
        if parent_task_id:
            properties[parent_task_prop] = {"relation": [{"id": parent_task_id}]}

        response = client.pages.create(
            parent={"database_id": NOTION_TASK_DATABASE_ID},
            properties=properties
        )
        return response["id"]
    except Exception as e:
        return f"Error creating task: {str(e)}"

def update_project(page_id: str, title: Optional[str] = None, status: Optional[str] = None, due_date: Optional[str] = None, goal: Optional[str] = None) -> str:
    client = _get_notion_client()
    if not client:
        return "Error: Notion Config missing."

    try:
        properties = {}
        if title:
             properties["Name"] = {"title": [{"text": {"content": title}}]}
        if status:
             properties["Status"] = {"status": {"name": status}}
        if goal:
             properties["Goal"] = {"rich_text": [{"text": {"content": goal}}]}
        if due_date:
             properties["Due Date"] = {"date": {"start": due_date}}
             
        if not properties:
            return "Error: No properties to update."

        response = client.pages.update(
            page_id=page_id,
            properties=properties
        )
        return response["id"]
    except Exception as e:
        return f"Error updating project: {str(e)}"

def update_task(
    page_id: str,
    title: Optional[str] = None, 
    status: Optional[str] = None, 
    priority: Optional[str] = None, 
    due_date: Optional[str] = None,
    parent_project_id: Optional[str] = None,
    parent_task_id: Optional[str] = None
) -> str:
    client = _get_notion_client()
    if not client or not NOTION_TASK_DATABASE_ID:
        return "Error: Notion Config missing."
    
    # We need schema to map property names correctly
    task_schema = NOTION_SCHEMA.get("Task", {})
    title_prop = "Task name" if "Task name" in task_schema else "Name"
    status_prop = "Status"
    priority_prop = "Priority"
    due_prop = "Due Date" if "Due Date" in task_schema else "Due"
    project_rel_prop = "Project"
    parent_task_prop = "Parent Task"

    try:
        properties = {}
        if title:
            properties[title_prop] = {"title": [{"text": {"content": title}}]}
        if status:
            properties[status_prop] = {"status": {"name": status}}
        if priority:
            properties[priority_prop] = {"select": {"name": priority}}
        if due_date:
            properties[due_prop] = {"date": {"start": due_date}}
        
        if parent_project_id:
            properties[project_rel_prop] = {"relation": [{"id": parent_project_id}]}
            
        if parent_task_id:
            properties[parent_task_prop] = {"relation": [{"id": parent_task_id}]}

        if not properties:
            return "Error: No properties to update."

        response = client.pages.update(
            page_id=page_id,
            properties=properties
        )
        return response["id"]
    except Exception as e:
        return f"Error updating task: {str(e)}"
