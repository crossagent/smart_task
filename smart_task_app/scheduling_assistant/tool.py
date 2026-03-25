from __future__ import annotations
import json
import os
from typing import Any, List, Dict
from google.adk.tools import FunctionTool, ToolContext
from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from smart_task_app.shared_libraries.constants import logger

# Database IDs from 5-Database Architecture
FEATURE_DB_ID = "32e0d59d-ebb7-8001-8bd0-000b1fd12363"
TASK_DB_ID = "32e0d59d-ebb7-8044-93e9-000ba6f9ab3d"
RESOURCE_DB_ID = "32e0d59d-ebb7-8070-a498-000b7430b8b1"

async def fetch_workload_and_resources(tool_context: ToolContext = None) -> str:
    """
    Fetch all active tasks, resource capacities, and feature target dates.
    Returns:
        A JSON string containing summarized 'tasks' (with feature_target_date) and 'resources'.
    """
    notion_mcp = get_notion_mcp_tool()
    
    # 1. Fetch active tasks (Status != Done)
    task_filter = {"property": "Status", "status": {"does_not_equal": "Done"}}
    try:
        tasks_data = await notion_mcp.call_tool("API-query-data-source", {"data_source_id": TASK_DB_ID, "filter": task_filter})
        tasks_raw = tasks_data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        tasks_raw = []

    # 2. Fetch all Features to build a Target_Date map
    feature_target_dates = {}
    try:
        features_data = await notion_mcp.call_tool("API-query-data-source", {"data_source_id": FEATURE_DB_ID})
        features_raw = features_data.get("results", [])
        for f in features_raw:
            td = f["properties"].get("Target_Date", {}).get("date", {}).get("start")
            if td:
                feature_target_dates[f["id"]] = td
    except Exception as e:
        logger.warning(f"Error fetching features: {e}")

    # 3. Fetch all Resources
    try:
        resources_data = await notion_mcp.call_tool("API-query-data-source", {"data_source_id": RESOURCE_DB_ID})
        resources_raw = resources_data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching resources: {e}")
        resources_raw = []

    # 4. Summarize for LLM (Reduce tokens)
    summarized_tasks = []
    for t in tasks_raw:
        props = t["properties"]
        feature_id = props.get("Feature", {}).get("relation", [{}])[0].get("id")
        
        # Extract Timeline Range
        timeline = props.get("Timeline", {}).get("date", {})
        current_start = timeline.get("start") if timeline else None
        current_due = timeline.get("end") if timeline else None
        
        summarized_tasks.append({
            "task_id": t["id"],
            "name": props.get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled"),
            "priority": props.get("Priority", {}).get("select", {}).get("name"),
            "est_hours": props.get("Estimated_Hours", {}).get("number"),
            "resource_id": props.get("Resource", {}).get("relation", [{}])[0].get("id"),
            "current_start": current_start,
            "current_due": current_due,
            "feature_id": feature_id,
            "feature_target_date": feature_target_dates.get(feature_id)
        })

    summarized_resources = []
    for r in resources_raw:
        props = r["properties"]
        summarized_resources.append({
            "resource_id": r["id"],
            "name": props.get("Name", {}).get("title", [{}])[0].get("plain_text", "Unnamed"),
            "weekly_capacity": props.get("Weekly_Capacity", {}).get("number", 40)
        })

    return json.dumps({
        "tasks": summarized_tasks,
        "resources": summarized_resources
    }, ensure_ascii=False)

async def apply_scheduling_results(schedule_json: str, tool_context: ToolContext = None) -> str:
    """
    Batch update the Task database with computed Timeline range.
    Args:
        schedule_json: A JSON list of objects: [{"task_id": "...", "start_date": "YYYY-MM-DD", "due": "YYYY-MM-DD"}]
    Returns:
        A success message or error details.
    """
    notion_mcp = get_notion_mcp_tool()
    updates = json.loads(schedule_json)
    
    results = []
    for item in updates:
        task_id = item.get("task_id")
        start_date = item.get("start_date")
        due_date = item.get("due")
        
        properties = {}
        if start_date and due_date:
            properties["Timeline"] = {
                "date": {
                    "start": start_date,
                    "end": due_date
                }
            }
        elif start_date: # Fallback if only start is provided
             properties["Timeline"] = {"date": {"start": start_date}}
            
        try:
            await notion_mcp.call_tool(
                "API-patch-page",
                {
                    "page_id": task_id,
                    "properties": properties
                }
            )
            results.append(f"Task {task_id} updated.")
        except Exception as e:
            results.append(f"Error updating task {task_id}: {str(e)}")
            
    return "\n".join(results)

# Exports
fetch_workload_and_resources_tool = FunctionTool(func=fetch_workload_and_resources)
apply_scheduling_results_tool = FunctionTool(func=apply_scheduling_results)
