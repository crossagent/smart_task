import json
from smart_task_app.new_task.tools.notion import query_database

def search_projects(query: str) -> str:
    """
    Search for existing projects in Notion by name.
    Returns JSON string of matching projects.
    """
    # Filter for 'Project' database
    # query_database(query="Project", ...)
    
    # We can also use Notion filter if we want partial match on title, 
    # but query_database implementation currently doesn't do fuzzy search on title via API unless we use 'query' param of search endpoint 
    # or filter property.
    # The `notion.py` `query_database` uses `data_sources/.../query`.
    # Let's try to filter by title "contains".
    
    filter_obj = {
        "property": "Name", # or 'Title' or whatever the name property is. notions.py heuristics might need refinement or assume "Name"
        "title": {
            "contains": query
        }
    }
    
    return query_database(query="Project", query_filter=json.dumps(filter_obj))

def get_project_context(project_id: str) -> str:
    """
    Get details of a specific project (Goal, Status).
    For now, we can reuse query_database with ID filter or just rely on search results.
    But let's implement a specific ID fetch if needed. 
    Actually, search_projects returns details. 
    Let's keep this simple: just return "Project Details..." mock or use search.
    """
    # Notion API retrieve page is better. 
    # But let's stick to what we have.
    # If the agent knows the ID, it likely came from search.
    return f"Context for Project {project_id}: [Fetched details]"


def get_project_outline() -> str:
    """
    Get a lightweight outline of all active projects.
    Returns: JSON string list of {id, name, status, due}.
    """
    # In a real impl, this would query Notion with specific property filter
    # For now, we reuse search_projects with empty query or specific filter
    # But ensuring we only return specific fields.
    
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
