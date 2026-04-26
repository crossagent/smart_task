from __future__ import annotations

import time
import json
import logging
import httpx
import threading
from typing import Optional, List, Dict, Any
from .db import execute_query, execute_mutation, db_transaction
from .supervisor import agent_supervisor

logger = logging.getLogger("smart_task.task_execution.scheduler")

# ==============================================================================
#  DATA PLANE DISPATCHER
# ==============================================================================

def dispatch_tasks(connection=None) -> dict:
    """Pure Worker Dispatch. Assigns ready tasks to available execution agents."""
    ready_tasks = execute_query("SELECT t.id, t.module_id, t.module_iteration_goal, m.owner_res_id FROM tasks t JOIN modules m ON t.module_id = m.id WHERE t.status = 'ready' ORDER BY t.id", connection=connection)
    available_resources = execute_query("SELECT id FROM resources WHERE is_available = True AND org_role != 'Control Plane' ORDER BY id", connection=connection)
    
    if not ready_tasks:
        return {"status": "no_tasks", "message": "No ready tasks to dispatch."}
        
    if not available_resources: 
        return {"status": "no_resources", "message": "No available execution agents."}

    dispatched = []
    res_pool = {r['id'] for r in available_resources}
    
    for task in ready_tasks:
        if not res_pool: break
        
        # Dispatch to owner or next available worker
        candidate = task['owner_res_id'] if task['owner_res_id'] in res_pool else next(iter(res_pool))
            
        if candidate:
            handle = agent_supervisor.pool.get(candidate)
            if not handle: continue
            
            execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task['id'],), connection=connection)
            execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (candidate,), connection=connection)
            execute_mutation("INSERT INTO task_assignments (task_id, resource_id, status) VALUES (%s, %s, 'active')", (task['id'], candidate), connection=connection)
            res_pool.remove(candidate)
            threading.Thread(target=_trigger_agent_async, args=(handle.url, handle.agent_id, task['id'], candidate, task['module_iteration_goal'])).start()
            dispatched.append({"task": task['id'], "agent": candidate})
            
    return {"status": "dispatched", "count": len(dispatched), "details": dispatched}

def _send_agent_request(url: str, agent_id: str, session_id: str, text: str):
    """Internal helper to send a POST request to an ADK agent."""
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(
                f"{url}/run", 
                json={
                    "app_name": agent_id, 
                    "session_id": session_id, 
                    "new_message": {"parts": [{"text": text}]}
                }
            )
    except Exception as e:
        logger.error(f"Agent request failed ({agent_id} @ {session_id}): {e}")

def _trigger_agent_async(url: str, agent_id: str, task_id: str, res_id: str, goal: str):
    """Triggers an execution agent for a specific task."""
    _send_agent_request(url, agent_id, task_id, goal)

def trigger_planner_async(url: str, agent_id: str, activity_id: str, instruction: str):
    """Specific trigger for the Plan-Agent to review an activity board."""
    _send_agent_request(url, agent_id, f"plan_{activity_id}", instruction)

