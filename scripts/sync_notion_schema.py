import os
import json
import sys
from notion_client import Client
from dotenv import load_dotenv

# Add project root to sys.path to allow importing if needed, though mostly standalone
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

NOTION_API_KEY = os.environ.get("NOTION_API_KEY")
NOTION_PROJECT_DATABASE_ID = os.environ.get("NOTION_PROJECT_DATABASE_ID")
NOTION_TASK_DATABASE_ID = os.environ.get("NOTION_TASK_DATABASE_ID")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'smart_task_app', 'data', 'notion_schema.json')

def get_database_properties(client, database_id):
    """Retrieves and simplifies properties from a Notion database."""
    try:
        # First try standard retrieve
        response = client.databases.retrieve(database_id=database_id)
        properties = response.get("properties", {})
        
        # If empty, try to infer from a page (common issue with some integrations/versions)
        if not properties:
            print(f"  Properties empty from retrieve, querying for a page to infer schema...")
            # Need data_source_id for query if using 2025-09-03? 
            # Actually, let's try standard query first.
            # Note: client.databases.query is deprecated/changed? 
            # In 2025-09-03, we might need data_source_id.
            
            # Get data_source_id
            data_sources = response.get("data_sources", [])
            print(f"  Data sources: {data_sources}")
            if data_sources:
                ds_id = data_sources[0]["id"]
                print(f"  Using Data Source ID: {ds_id}")
                # Query using data_source_id
                query_response = client.request(
                    method="POST",
                    path=f"data_sources/{ds_id}/query",
                    body={"page_size": 1}
                )
                results = query_response.get("results", [])
                print(f"  Query results count: {len(results)}")
                if results:
                    properties = results[0].get("properties", {})
                    print(f"  Inferred {len(properties)} properties from page.")
            else:
                 print("  No data sources found, cannot query.")
        else:
            print(f"  Retrieved {len(properties)} properties directly.")

        simplified_props = {}
        for name, prop in properties.items():
            prop_type = prop["type"]
            prop_info = {"type": prop_type}
            
            # Extract options for select, multi_select, and status
            if prop_type in ["select", "multi_select"]:
                options = prop[prop_type].get("options", [])
                prop_info["options"] = [opt["name"] for opt in options]
            elif prop_type == "status":
                options = prop[prop_type].get("options", [])
                prop_info["options"] = [opt["name"] for opt in options]
            
            simplified_props[name] = prop_info
            
        return simplified_props
    except Exception as e:
        print(f"Error retrieving database {database_id}: {e}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    if not NOTION_API_KEY:
        print("Error: NOTION_API_KEY not found in .env")
        return

    print("Initializing Notion Client...")
    client = Client(auth=NOTION_API_KEY, notion_version="2022-06-28")
    
    schema = {
        "Project": {},
        "Task": {}
    }

    if NOTION_PROJECT_DATABASE_ID:
        print(f"Fetching Project Database Schema ({NOTION_PROJECT_DATABASE_ID})...")
        schema["Project"] = get_database_properties(client, NOTION_PROJECT_DATABASE_ID)
    
    if NOTION_TASK_DATABASE_ID:
        print(f"Fetching Task Database Schema ({NOTION_TASK_DATABASE_ID})...")
        schema["Task"] = get_database_properties(client, NOTION_TASK_DATABASE_ID)

    print(f"Saving schema to {OUTPUT_FILE}...")
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)
    
    print("Schema synchronization complete.")

if __name__ == "__main__":
    main()
