from __future__ import annotations
import json
import os
from typing import Any, List, Dict
from google.adk.tools import FunctionTool, ToolContext
from smart_task_app.shared_libraries.logseq_util import get_logseq_mcp_tool
from smart_task_app.shared_libraries.constants import logger

# Logseq Classes for 5-Database Architecture
FEATURE_CLASS = "[[Feature]]"
TASK_CLASS = "[[Task]]"
RESOURCE_CLASS = "[[Resource]]"

async def fetch_workload_and_resources(tool_context: ToolContext = None) -> str:
    """
    Fetch all active tasks, resource capacities, and feature target dates from Logseq.
    """
    logseq_mcp = get_logseq_mcp_tool()
    tools = await logseq_mcp.get_tools()
    
    # helper to call tool
    async def call_tool(name, args):
        t = next(t for t in tools if t.name == name)
        res = await t.run_async(args=args, tool_context=tool_context)
        if hasattr(res, "content"):
            return json.loads(res.content[0].text)
        return json.loads(res)

    # 1. Fetch active tasks (status != [[Done]])
    try:
        tasks_data = await call_tool("search", {"query": f"class:: {TASK_CLASS} -status:: [[Done]]"})
        tasks_raw = tasks_data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        tasks_raw = []

    # 2. Fetch all Features to build a Target_Date map
    feature_target_dates = {}
    try:
        features_data = await call_tool("search", {"query": f"class:: {FEATURE_CLASS}"})
        features_raw = features_data.get("results", [])
        for f in features_raw:
            td = f.get("properties", {}).get("target-date")
            if td:
                feature_target_dates[f.get("uuid")] = td
    except Exception as e:
        logger.warning(f"Error fetching features: {e}")

    # 3. Fetch all Resources
    try:
        resources_data = await call_tool("search", {"query": f"class:: {RESOURCE_CLASS}"})
        resources_raw = resources_data.get("results", [])
    except Exception as e:
        logger.error(f"Error fetching resources: {e}")
        resources_raw = []

    # 4. Summarize for LLM
    summarized_tasks = []
    for t in tasks_raw:
        props = t.get("properties", {})
        # Logseq properties are usually lower-case-with-hyphens or as defined in class
        feature_ref = props.get("feature", "")
        feature_uuid = feature_ref.strip("() ") if feature_ref.startswith("((") else None
        
        summarized_tasks.append({
            "task_id": t.get("uuid"),
            "name": t.get("content", "").split("\n")[0],
            "priority": props.get("priority"),
            "est_hours": float(props.get("estimated-hours", 0)),
            "resource_id": props.get("resource", "").strip("() "),
            "current_start": props.get("start-date"),
            "current_due": props.get("due-date"),
            "feature_id": feature_uuid,
            "feature_target_date": feature_target_dates.get(feature_uuid)
        })

    summarized_resources = []
    for r in resources_raw:
        props = r.get("properties", {})
        summarized_resources.append({
            "resource_id": r.get("uuid"),
            "name": r.get("content", "").split("\n")[0],
            "weekly_capacity": float(props.get("weekly-capacity", 40))
        })

    return json.dumps({
        "tasks": summarized_tasks,
        "resources": summarized_resources
    }, ensure_ascii=False)

async def apply_scheduling_results(schedule_json: str, tool_context: ToolContext = None) -> str:
    """
    Batch update the Logseq blocks with computed dates.
    Args:
        schedule_json: A JSON list of objects: [{"task_id": "...", "start_date": "YYYY-MM-DD", "due": "YYYY-MM-DD"}]
    """
    logseq_mcp = get_logseq_mcp_tool()
    updates = json.loads(schedule_json)
    
    results = []
    for item in updates:
        task_uuid = item.get("task_id")
        start_date = item.get("start_date")
        due_date = item.get("due")
        
        try:
            if start_date:
                await logseq_mcp.call_tool("upsert_block_property", {"block_uuid": task_uuid, "property": "start-date", "value": start_date})
            if due_date:
                await logseq_mcp.call_tool("upsert_block_property", {"block_uuid": task_uuid, "property": "due-date", "value": due_date})
            
            results.append(f"Task {task_uuid} scheduled.")
        except Exception as e:
            results.append(f"Error scheduling task {task_uuid}: {str(e)}")
            
    return "\n".join(results)

# Exports
fetch_workload_and_resources_tool = FunctionTool(func=fetch_workload_and_resources)
apply_scheduling_results_tool = FunctionTool(func=apply_scheduling_results)
