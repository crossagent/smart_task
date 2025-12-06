import os
import json
from typing import Optional, Dict, Any, List
from notion_client import Client
from dotenv import load_dotenv

# Load env vars from root .env
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'))

# Initialize Notion client
# We use the new 2025-09-03 version which requires data_source_id for many operations.
NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_PROJECT_DATABASE_ID = os.environ.get("NOTION_PROJECT_DATABASE_ID")
NOTION_TASK_DATABASE_ID = os.environ.get("NOTION_TASK_DATABASE_ID")

# Global cache for data source ID to avoid fetching it on every request
_DATA_SOURCE_ID_CACHE = {}

# Load schema
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'notion_schema.json')
NOTION_SCHEMA = {}
if os.path.exists(SCHEMA_PATH):
    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            NOTION_SCHEMA = json.load(f)
    except Exception as e:
        print(f"Error loading Notion schema: {e}")

def _get_notion_client() -> Optional[Client]:
    """
    Returns a Notion Client configured with the correct API version.
    """
    if not NOTION_API_KEY:
        return None
    return Client(auth=NOTION_API_KEY, notion_version="2025-09-03")

def _get_data_source_id(client: Client, database_id: str) -> Optional[str]:
    """
    Resolves the database_id to a data_source_id using the 2025-09-03 API.
    This is required because the new API version treats databases as data sources.
    """
    global _DATA_SOURCE_ID_CACHE
    if database_id in _DATA_SOURCE_ID_CACHE:
        return _DATA_SOURCE_ID_CACHE[database_id]

    try:
        # GET /v1/databases/{database_id}
        # The client automatically handles the base URL.
        # We need to ensure we are using the correct version which is set in the client init.
        response = client.databases.retrieve(database_id=database_id)
        
        # Check for data_sources
        data_sources = response.get("data_sources", [])
        if data_sources:
            # Use the first data source
            ds_id = data_sources[0]["id"]
            _DATA_SOURCE_ID_CACHE[database_id] = ds_id
            return ds_id
        else:
            print(f"[Notion] No data sources found for database {database_id}")
            return None
    except Exception as e:
        print(f"[Notion] Error retrieving database {database_id}: {e}")
        return None

def get_database_schema(database_name: str) -> str:
    """
    Returns the schema for a given database table.
    Args:
        database_name: 'Project' or 'Task'
    """
    if database_name in NOTION_SCHEMA:
        return json.dumps(NOTION_SCHEMA[database_name], indent=2, ensure_ascii=False)
    
    return json.dumps({"error": f"Database {database_name} not found in schema definition."})

def query_database(query: str) -> str:
    """
    Executes a SQL-like query against the Notion databases.
    Supported syntax: SELECT * FROM [Table] WHERE [Condition]
    Example: "SELECT * FROM Task WHERE status = 'In Progress'"
    """
    client = _get_notion_client()
    if not client:
        return json.dumps({"error": "Notion API key not configured."})

    # Determine database
    database_id = None
    if "from project" in query.lower():
        database_id = NOTION_PROJECT_DATABASE_ID
    elif "from task" in query.lower():
        database_id = NOTION_TASK_DATABASE_ID
    
    if not database_id:
        return json.dumps({"error": "Could not determine database from query. Use 'FROM Project' or 'FROM Task'."})

    # Get Data Source ID
    data_source_id = _get_data_source_id(client, database_id)
    if not data_source_id:
        return json.dumps({"error": "Could not resolve Data Source ID."})

    try:
        # TODO: Implement actual SQL-to-Notion-Filter parsing
        # For now, just fetch recent items
        response = client.request(
            method="POST",
            path=f"data_sources/{data_source_id}/query",
            body={"page_size": 10}
        )
        
        results = response.get("results", [])
        simplified_results = []
        for page in results:
            props = page.get("properties", {})
            item = {"id": page["id"]}
            
            # Extract common fields
            # Note: This depends on the actual property names in Notion
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

def _find_property_name_by_type(schema, prop_type):
    for name, info in schema.items():
        if info["type"] == prop_type:
            return name
    return None

def add_task_to_database(title: str, status: Optional[str] = None, priority: Optional[str] = None, due_date: Optional[str] = None) -> str:
    """
    Adds a new task to the Notion Task database.
    """
    client = _get_notion_client()
    if not client or not NOTION_TASK_DATABASE_ID:
        return "Error: Notion API Key or Task Database ID not configured."

    # Use data_source_id for 2025-09-03
    data_source_id = _get_data_source_id(client, NOTION_TASK_DATABASE_ID)
    if not data_source_id:
        return "Error: Could not resolve Task Data Source ID."

    task_schema = NOTION_SCHEMA.get("Task", {})
    
    # Resolve property names dynamically
    title_prop = _find_property_name_by_type(task_schema, "title") or "Name"
    status_prop = "Status" # Usually named Status, but could check type 'status'
    priority_prop = "Priority" # Usually named Priority
    due_prop = "Due" # Usually named Due or Date
    
    # Better dynamic resolution if possible, but fallback to known keys from schema if available
    if "Task name" in task_schema: title_prop = "Task name"
    if "Due" in task_schema: due_prop = "Due"
    if "Due Date" in task_schema: due_prop = "Due Date"

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

        # Use client.pages.create
        response = client.pages.create(
            parent={"database_id": NOTION_TASK_DATABASE_ID},
            properties=properties
        )
        return response["id"]
    except Exception as e:
        return f"Error creating task: {str(e)}"
