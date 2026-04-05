import threading
import time
import subprocess
import os

from mcp.server.fastmcp import FastMCP
from src.task_management.db import execute_query, execute_mutation

def run_scheduler_tick():
    """Runs a single pass of the scheduler logic. Useful for testing."""
    try:
        # 1. Promote pending tasks
        pending_tasks = execute_query("SELECT id, depends_on FROM tasks WHERE status = 'pending'")
        for task in pending_tasks:
            task_id = task['id']
            depends_on = task['depends_on'] or []
            
            if not depends_on:
                # No dependencies -> ready
                execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
                print(f">>> [Scheduler] Promoted {task_id} to ready (No dependencies).")
                continue
            
            # Check status of dependencies
            placeholders = ','.join(['%s']*len(depends_on))
            chk_query = f"SELECT id, status FROM tasks WHERE id IN ({placeholders})"
            deps = execute_query(chk_query, tuple(depends_on))
            
            if len(deps) == len(depends_on) and all(d['status'] == 'done' for d in deps):
                execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
                print(f">>> [Scheduler] Promoted {task_id} to ready (Dependencies met).")

        # 2. Dispatch ready tasks
        ready_tasks = execute_query("""
            SELECT 
                t.id as task_id, 
                r.id as res_id, 
                r.resource_type, 
                r.agent_dir, 
                r.workspace_path, 
                r.is_available 
            FROM tasks t
            JOIN resources r ON t.resource_id = r.id
            WHERE t.status = 'ready'
        """)
        
        for task in ready_tasks:
            if task['is_available']:
                task_id = task['task_id']
                res_id = task['res_id']
                agent_dir = task['agent_dir']
                workspace_path = task['workspace_path']
                
                # Mark resource busy, task in_progress
                execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,))
                execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (task_id,))
                
                print(f">>> [Scheduler] Dispatching Task {task_id} to Resource {res_id} (Agent: {agent_dir})")
                
                # Start asynchronous dispatch
                threading.Thread(
                    target=run_agent_subprocess,
                    args=(task_id, res_id, agent_dir, workspace_path),
                    daemon=True
                ).start()
                
    except Exception as e:
        print(f">>> [Scheduler] Error in tick: {e}")

def scheduler_daemon():
    """
    Background loop that:
    1. Promotes 'pending' tasks to 'ready' if all their depends_on tasks are 'done'.
    2. Dispatches 'ready' tasks to available resources by triggering ADK agents via subprocess.
    """
    print(">>> [Scheduler] Daemon started.")
    while True:
        run_scheduler_tick()
        time.sleep(5)

def run_agent_subprocess(task_id: str, res_id: str, agent_dir: str, workspace_path: str):
    """Execution wrapper for the ADK agent. Once completed, releases the resource."""
    try:
        # Pass context entirely via Env variables.
        env = os.environ.copy()
        env['SMART_TASK_ID'] = task_id
        if workspace_path:
            env['SMART_WORKSPACE_PATH'] = workspace_path
        
        # If no agent_dir provided, just mock execution for 5 seconds
        if not agent_dir:
            print(f"    [Agent Runner] No agent_dir for {res_id}, mocking execution...")
            time.sleep(5)
            # Normally the agent updates its own state, since no agent, we mock complete
            execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = %s", (task_id,))
        else:
            # Execute ADK CLI logic
            print(f"    [Agent Runner] Spawning ADK agent from {agent_dir}...")
            cmd = ["uv", "run", "adk", "run", agent_dir]
            
            process = subprocess.Popen(
                cmd, 
                env=env,
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                text=True
            )
            for line in process.stdout:
                # Log agent output
                print(f"[{res_id}] {line}", end="")
            process.wait()
            
            if process.returncode != 0:
                execute_mutation("UPDATE tasks SET status = 'failed' WHERE id = %s", (task_id,))
                print(f">>> [Scheduler] Task {task_id} FAILED (Exit code: {process.returncode})")
            else:
                # Safety net: if agent didn't update status, mark as code_done
                execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = %s AND status = 'in_progress'", (task_id,))
                print(f">>> [Scheduler] Task {task_id} completed successfully.")
            
    except Exception as e:
        print(f"    [Agent Runner] Error running agent for task {task_id}: {e}")
    finally:
        # Free up the resource
        execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (res_id,))
        print(f">>> [Scheduler] Resource {res_id} freed.")
