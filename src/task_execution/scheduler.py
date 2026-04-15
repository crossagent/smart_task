from __future__ import annotations

import time
import logging
import httpx
import threading
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

        # 4. Monitor activity health and trigger activity manager if stalled
        _monitor_activities()
                
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
        handle = agent_supervisor.pool.get(res_id)
        if not handle:
            logger.warning(f"Task {task_id} deferred: Resource {res_id} not found in persistent pool.")
            continue
        
        agent_url = handle.url
        agent_id = handle.agent_id

        # Attempt to lock the physical Workspace
        if not workspace_lock_manager.try_lock(workspace_path, task_id):
            logger.warning(f"Task {task_id} deferred: Workspace {workspace_path} is currently locked.")
            continue

        # Atomically mark resource as busy and task as in_progress
        execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,))
        execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task_id,))
        
        logger.info(f"Dispatching Task {task_id} to Persistent Agent {res_id} at {agent_url}")
        
        # Trigger execution via HTTP (Async - Fire and Forget)
        threading.Thread(target=self_trigger_agent, args=(agent_url, agent_id, res_id, task_id, goal), daemon=True).start()

def self_trigger_agent(url: str, agent_id: str, res_id: str, task_id: str, goal: str):
    """Sends the invocation request to the Agent's API."""
    try:
        # 1. Ensure Session exists on the Agent server
        session_init_url = f"{url}/apps/{agent_id}/users/smart-task-scheduler/sessions"
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(session_init_url, json={"session_id": task_id})
        except Exception as e:
            logger.warning(f"Session initialization warning (non-fatal): {e}")

        # 2. Standard payload for ADK api_server /run endpoint
        payload = {
            "app_name": agent_id,
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

def _monitor_activities():
    """
    Checks if any active Activities have completely stalled or finished.
    If so, summons the Activity Manager to analyze results and decide next steps.
    """
    query = """
        SELECT a.id, a.project_id, m.id as root_module_id,
               COUNT(t.id) as total_tasks,
               COUNT(CASE WHEN t.status IN ('done', 'code_done') THEN 1 END) as completed,
               COUNT(CASE WHEN t.status IN ('failed', 'blocked') THEN 1 END) as issues,
               COUNT(CASE WHEN t.status IN ('pending', 'ready', 'in_progress', 'needs_human_help') THEN 1 END) as active
        FROM activities a
        JOIN tasks t ON a.id = t.activity_id
        JOIN modules m ON t.module_id = m.id AND m.parent_module_id IS NULL
        WHERE a.status = 'Active'
        GROUP BY a.id, a.project_id, m.id
        HAVING COUNT(CASE WHEN t.status IN ('pending', 'ready', 'in_progress', 'needs_human_help') THEN 1 END) = 0
    """
    stalled_activities = execute_query(query)
    
    for act in stalled_activities:
        act_id = act['id']
        project_id = act['project_id']
        root_module_id = act['root_module_id']
        rev_task_id = f"REV-{act_id}"
        
        # Check if intervention task already exists
        exist_check = execute_query("SELECT id FROM tasks WHERE id = %s", (rev_task_id,))
        if exist_check:
            continue
            
        logger.warning(f"Activity {act_id} stalled/finished. Summoning Activity Manager.")
        
        goal = (f"Review Activity {act_id}. All subtasks are terminal. "
                f"Completed: {act['completed']}/{act['total_tasks']}. Issues: {act['issues']}. "
                "Analyze the execution results and either officially close the Activity or break down new tasks to fix issues.")
                
        # Insert a special Intervention Task for the Activity Manager
        sql = """
            INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                               module_iteration_goal, estimated_hours, status)
            VALUES (%s, %s, %s, %s, 'RES-ARCHITECT-001', %s, 1.0, 'ready')
        """
        try:
            execute_mutation(sql, (rev_task_id, project_id, act_id, root_module_id, goal))
            logger.info(f"Created intervention task {rev_task_id} for Activity Manager.")
        except Exception as e:
            logger.error(f"Failed to create intervention task for {act_id}: {e}")

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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent_supervisor.load_config()
    scheduler_daemon()
