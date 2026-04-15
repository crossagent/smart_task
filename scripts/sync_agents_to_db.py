from __future__ import annotations
import yaml
import os
from src.task_management.db import execute_mutation, execute_query

def sync_resources():
    config_path = "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    agents_pool = config.get("agents_pool", [])
    
    # Get existing resource IDs
    existing = {r['id'] for r in execute_query("SELECT id FROM resources")}
    
    for agent in agents_pool:
        res_id = agent["resource_id"]
        name = agent["name"]
        workspace = agent["default_workspace"]
        
        if res_id in existing:
            print(f"Updating resource {res_id} ({name})")
            execute_mutation(
                "UPDATE resources SET name = %s, workspace_path = %s, is_available = True WHERE id = %s",
                (name, workspace, res_id)
            )
        else:
            print(f"Inserting resource {res_id} ({name})")
            execute_mutation(
                "INSERT INTO resources (id, name, type, workspace_path, is_available) VALUES (%s, %s, 'agent', %s, True)",
                (res_id, name, workspace)
            )

if __name__ == "__main__":
    sync_resources()
