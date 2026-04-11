from __future__ import annotations

import time
import logging
from src.task_management.db import execute_query, execute_mutation
from src.resource_management.workspace_lock import workspace_lock_manager
from src.resource_management.supervisor import agent_supervisor

logger = logging.getLogger("smart_task.task_execution.scheduler")

def run_scheduler_tick():
    """Runs a single pass of the scheduler logic."""
    try:
        # 1. Promote pending tasks to ready if dependencies are met
        _promote_pending_tasks()

        # 2. Dispatch ready tasks to available agents and workspaces
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
        
        if len(deps) == len(depends_on) and all(d['status'] == 'done' for d in deps):
            execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
            logger.info(f"Promoted {task_id} to ready (Dependencies met).")

def _dispatch_ready_tasks():
    # Only pick tasks where the assigned resource is currently available
    ready_tasks = execute_query("""
        SELECT 
            t.id as task_id, 
            r.id as res_id, 
            r.agent_dir, 
            r.workspace_path
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status = 'ready' AND r.is_available = True
    """)
    
    for task in ready_tasks:
        task_id = task['task_id']
        res_id = task['res_id']
        agent_dir = task['agent_dir']
        workspace_path = task['workspace_path']
        
        # Attempt to lock the physical Workspace
        if not workspace_lock_manager.try_lock(workspace_path, task_id):
            logger.warning(f"Task {task_id} deferred: Workspace {workspace_path} is currently locked.")
            continue

        # Atomically mark resource as busy and task as in_progress
        # (In a high-concurrency env, we'd use a transaction here)
        execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,))
        execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task_id,))
        
        logger.info(f"Dispatching Task {task_id} to Machine {res_id} on Workspace {workspace_path}")
        
        # Launch Agent via Supervisor
        handle = agent_supervisor.dispatch(task_id, res_id, agent_dir, workspace_path)
        
        # Register cleanup callback
        handle.on_complete(lambda h, rp=workspace_path, ri=res_id: _cleanup_task_resources(rp, ri))

def _cleanup_task_resources(workspace_path: str, resource_id: str):
    """Callback to release locks after agent completion."""
    try:
        # 1. Release Workspace Lock
        workspace_lock_manager.unlock(workspace_path)
        
        # 2. Free up the Machine/Agent Resource
        execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (resource_id,))
        logger.info(f"Cleaned up resources for Machine {resource_id} and Workspace {workspace_path}")
    except Exception as e:
        logger.error(f"Cleanup error for resource {resource_id}: {e}")

def scheduler_daemon():
    """Background loop for continuous scheduling."""
    logger.info("Scheduler Daemon started.")
    while True:
        run_scheduler_tick()
        time.sleep(5)
