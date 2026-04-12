from __future__ import annotations

import time
import logging
import httpx
from src.task_management.db import execute_query, execute_mutation
from src.resource_management.workspace_lock import workspace_lock_manager
from src.resource_management.supervisor import agent_supervisor

logger = logging.getLogger("smart_task.task_execution.scheduler")

def run_scheduler_tick():
    """Runs a single pass of the scheduler logic."""
    try:
        # 1. Promote pending tasks to ready if dependencies are met
        _promote_pending_tasks()

        # 2. Reconcile completed tasks to release resources
        _reconcile_completed_tasks()

        # 3. Dispatch ready tasks to persistent agent pool
        _dispatch_ready_tasks()
                
    except Exception as e:
        logger.error(f"Error in scheduler tick: {e}")

def _promote_pending_tasks():
    pending_tasks = execute_query("SELECT id, depends_on FROM tasks WHERE status = 'pending'")
    for task in pending_tasks:
        task_id = task['id']
        depends_on = task['depends_on'] or []
        
        if not depends_on:
            execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
            logger.info(f"Promoted {task_id} to ready (No dependencies).")
            continue
        
        # Check status of dependencies
        placeholders = ','.join(['%s']*len(depends_on))
        chk_query = f"SELECT id, status FROM tasks WHERE id IN ({placeholders})"
        deps = execute_query(chk_query, tuple(depends_on))
        
        # Only ready if all deps are 'done' (or similar final state)
        if len(deps) == len(depends_on) and all(d['status'] in ('done', 'code_done') for d in deps):
            execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
            logger.info(f"Promoted {task_id} to ready (Dependencies met).")

def _reconcile_completed_tasks():
    """Checks for tasks that finished execution and releases their resource/locks."""
    # Find tasks that are done but the resource is still marked as busy
    # Note: This is a simplified reconciliation.
    completed_tasks = execute_query("""
        SELECT t.id, t.resource_id, r.workspace_path
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status IN ('done', 'code_done', 'failed') AND r.is_available = False
    """)
    
    for task in completed_tasks:
        task_id = task['id']
        res_id = task['resource_id']
        workspace_path = task['workspace_path']
        
        logger.info(f"Reconciling completed task {task_id}. Releasing resource {res_id}.")
        _cleanup_task_resources(workspace_path, res_id)

def _dispatch_ready_tasks():
    # Only pick tasks where the assigned resource is currently available in the pool
    ready_tasks = execute_query("""
        SELECT 
            t.id as task_id, 
            r.id as res_id, 
            r.workspace_path,
            t.module_iteration_goal
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status = 'ready' AND r.is_available = True
    """)
    
    for task in ready_tasks:
        task_id = task['task_id']
        res_id = task['res_id']
        workspace_path = task['workspace_path']
        goal = task['module_iteration_goal']
        
        # Check if the agent is actually up in the pool
        agent_url = agent_supervisor.get_agent_url(res_id)
        if not agent_url:
            logger.warning(f"Task {task_id} deferred: Resource {res_id} not found in persistent pool.")
            continue

        # Attempt to lock the physical Workspace
        if not workspace_lock_manager.try_lock(workspace_path, task_id):
            logger.warning(f"Task {task_id} deferred: Workspace {workspace_path} is currently locked.")
            continue

        # Atomically mark resource as busy and task as in_progress
        execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,))
        execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task_id,))
        
        logger.info(f"Dispatching Task {task_id} to Persistent Agent {res_id} at {agent_url}")
        
        # Trigger execution via HTTP (Async - Fire and Forget)
        threading.Thread(target=self_trigger_agent, args=(agent_url, task_id, res_id, goal), daemon=True).start()

def self_trigger_agent(url: str, task_id: str, res_id: str, goal: str):
    """Sends the invocation request to the Agent's API."""
    try:
        # 1. Ensure Session exists on the Agent server
        session_init_url = f"{url}/apps/{res_id}/users/smart-task-scheduler/sessions"
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(session_init_url, json={"session_id": task_id})
        except Exception as e:
            logger.warning(f"Session initialization warning (non-fatal): {e}")

        # 2. Standard payload for ADK api_server /run endpoint
        payload = {
            "app_name": res_id,
            "user_id": "smart-task-scheduler",
            "session_id": task_id,
            "new_message": {"parts": [{"text": f"Current Task ID: {task_id}. Your goal: {goal}"}]}
        }
        
        with httpx.Client(timeout=60.0) as client:
            response = client.post(f"{url}/run", json=payload)
            response.raise_for_status()
            logger.info(f"Task {task_id} successfully triggered on {url}")
    except Exception as e:
        logger.error(f"Failed to trigger agent at {url} for task {task_id}: {e}")
        # Revert status to ready if trigger failed so it can be retried
        execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
        execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (res_id,))

def _cleanup_task_resources(workspace_path: str, resource_id: str):
    """Releases locks and marks resource as available."""
    try:
        workspace_lock_manager.unlock(workspace_path)
        execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (resource_id,))
        logger.info(f"Cleaned up resources for Agent {resource_id} and Workspace {workspace_path}")
    except Exception as e:
        logger.error(f"Cleanup error for resource {resource_id}: {e}")

def scheduler_daemon():
    """Background loop for continuous scheduling."""
    logger.info("Scheduler Daemon started.")
    while True:
        run_scheduler_tick()
        time.sleep(5)

import threading # Ensure threading is available for the trigger thread
