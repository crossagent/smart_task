from __future__ import annotations

import time
import os
import logging
import httpx
import threading
from src.task_management.db import execute_query, execute_mutation, db_transaction
from src.resource_management.workspace_lock import workspace_lock_manager
from src.resource_management.supervisor import agent_supervisor

logger = logging.getLogger("smart_task.task_execution.scheduler")

def run_system_bus_cycle():
    """
    Core System Control Bus Cycle.
    Follows: [Priority 0: Interrupts] -> [Priority 1: DAG Data Plane] -> [Priority 2: Reconcile]
    """
    try:
        with db_transaction() as conn:
            # 1. PRIORITY 0: Monitor systems for anomalies
            _watch_for_interrupts(connection=conn)
            
            # 1.1 Monitor for Human Interventions (Manual Goal Changes)
            _watch_for_human_interventions(connection=conn)

            # 2. PRIORITY 1: Control Gate (Pause/Step Logic)
            # Fetch global system state
            state_data = execute_query("SELECT key, value FROM system_state", connection=conn)
            state = {row['key']: row['value'] for row in state_data}
            
            run_mode = state.get('run_mode', "auto")
            # JSONB strings might have extra quotes or be plain
            if isinstance(run_mode, str):
                run_mode = run_mode.strip('"') 
            
            step_count = int(state.get('step_count', 0))

            # Decide whether to run execution logic
            if run_mode == "pause" and step_count <= 0:
                logger.debug("System Bus Cycle: GATED/PAUSED. Skipping execution logic.")
            else:
                if step_count > 0:
                    logger.info(f"System Bus Cycle: STEP mode ({step_count} remaining). Executing...")
                    execute_mutation("UPDATE system_state SET value = %s WHERE key = 'step_count'", (str(step_count - 1),), connection=conn)

                # 3. PRIORITY 1: Data Plane flow
                # Promote pending tasks to ready if dependencies are met
                _promote_pending_tasks(connection=conn)
                
                # Dispatch ready tasks to persistent agent pool (Execution start)
                _dispatch_ready_tasks(connection=conn)

            # 4. PRIORITY 2: System Health & Maintenance
            # Reconcile active locks and clear stale entries
            _reconcile_active_locks(connection=conn)

            # Reconcile completed tasks to release resources
            _reconcile_completed_tasks(connection=conn)
            
            # Monitor activity health and trigger activity manager if stalled (Legacy fallback)
            _monitor_activities(connection=conn)
                
    except Exception as e:
        logger.error(f"Error in system bus cycle: {e}")

def _watch_for_human_interventions(connection=None):
    """
    Detects if the user has manually updated the activity instructions.
    If so, fires a high-priority 'INT-EVT-HUMAN' interrupt Task to the PM.
    """
    try:
        # Check all active activities for instruction updates
        updated_activities = execute_query("""
            SELECT a.id, a.project_id, a.user_instruction, a.instruction_version
            FROM activities a
            LEFT JOIN system_state s ON s.key = 'last_human_irq_' || a.id
            WHERE a.status = 'Active' 
              AND a.instruction_version > COALESCE((s.value->>0)::int, -1)
        """, connection=connection)

        for act in updated_activities:
            act_id = act['id']
            proj_id = act['project_id']
            instr = act['user_instruction'] or "No specific instruction provided."
            version = act['instruction_version']
            
            interrupt_id = f"INT-EVT-HUMAN-{act_id}-V{version}"
            
            logger.warning(f"HUMAN INTERCEPTION: User updated instructions for Activity {act_id}. Signaling Bus.")

            goal = (f"HUMAN COMMAND RECEIVED (Version {version}):\n\n"
                    f"\"{instr}\"\n\n"
                    "As the Control Plane, you must now re-evaluate your current DAG plan. "
                    "Use your tools to adjust task goals, add new nodes, or reset states to satisfy the user's new requirements.")

            # Insert Interrupt (Independent)
            sql = """
                INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                                   module_iteration_goal, estimated_hours, status)
                SELECT %s, %s, %s, t.module_id, 'RES-ARCHITECT-001', %s, 0.5, 'ready'
                FROM tasks t WHERE t.activity_id = %s LIMIT 1
                ON CONFLICT (id) DO NOTHING
            """
            execute_mutation(sql, (interrupt_id, proj_id, act_id, goal, act_id), connection=connection)
            
            # Record that we've processed this version
            execute_mutation("""
                INSERT INTO system_state (key, value) 
                VALUES ('last_human_irq_' || %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (act_id, str(version)), connection=connection)

    except Exception as e:
        logger.error(f"Failed to check for human interventions: {e}")

def _promote_pending_tasks(connection=None):
    pending_tasks = execute_query("SELECT id, depends_on, is_approved FROM tasks WHERE status = 'pending'", connection=connection)
    for task in pending_tasks:
        task_id = task['id']
        depends_on = task['depends_on'] or []
        is_approved = task['is_approved']
        
        target_status = 'ready' if is_approved else 'awaiting_approval'
        
        if not depends_on:
            execute_mutation("UPDATE tasks SET status = %s WHERE id = %s", (target_status, task_id), connection=connection)
            logger.info(f"Promoted {task_id} to {target_status} (No dependencies).")
            continue
        
        # Check status of dependencies
        placeholders = ','.join(['%s']*len(depends_on))
        chk_query = f"SELECT id, status FROM tasks WHERE id IN ({placeholders})"
        deps = execute_query(chk_query, tuple(depends_on), connection=connection)
        
        # Only promote if all deps are 'done' (or similar final state)
        if len(deps) == len(depends_on) and all(d['status'] in ('done', 'code_done') for d in deps):
            execute_mutation("UPDATE tasks SET status = %s WHERE id = %s", (target_status, task_id), connection=connection)
            logger.info(f"Promoted {task_id} to {target_status} (Dependencies met).")

def _reconcile_completed_tasks(connection=None):
    """Checks for tasks that finished execution and releases their resource/locks."""
    # Find tasks that are done but the resource is still marked as busy
    # Note: This is a simplified reconciliation.
    completed_tasks = execute_query("""
        SELECT t.id, t.resource_id, r.workspace_path
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status IN ('done', 'code_done', 'failed') AND r.is_available = False
    """, connection=connection)
    
    for task in completed_tasks:
        task_id = task['id']
        res_id = task['resource_id']
        workspace_path = task['workspace_path']
        
        logger.info(f"Reconciling completed task {task_id}. Releasing resource {res_id}.")
        _cleanup_task_resources(workspace_path, res_id, connection=connection)

        # AUTO-RECONCILE: If this was a Lead Task, also mark its bundled siblings as done
        execute_mutation("""
            UPDATE tasks SET status = 'done', updated_at = CURRENT_TIMESTAMP 
            WHERE parent_interrupt_id = %s AND status = 'ready'
        """, (task_id,), connection=connection)

def _dispatch_ready_tasks(connection=None):
    # 1. Grab all ready tasks
    all_ready = execute_query("""
        SELECT 
            t.id as task_id, 
            r.id as res_id, 
            r.workspace_path,
            t.module_iteration_goal
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status = 'ready' AND r.is_available = True
    """, connection=connection)

    # 2. Group by Resource
    from collections import defaultdict
    tasks_by_res = defaultdict(list)
    for t in all_ready:
        tasks_by_res[t['res_id']].append(t)

    # 3. Dispatch Grouped
    for res_id, tasks in tasks_by_res.items():
        # Check if the agent is actually up in the pool
        handle = agent_supervisor.pool.get(res_id)
        if not handle:
            logger.warning(f"Task {tasks[0]['task_id']} deferred: Resource {res_id} not found in persistent pool.")
            continue
            
        # Lead Task Selection
        lead = tasks[0]
        lead_id = lead['task_id']
        workspace_path = lead['workspace_path']
        final_goal = lead['module_iteration_goal']
        
        # Batching/Bundling Logic
        bundled_ids = [t['task_id'] for t in tasks[1:]]
        if bundled_ids:
            logger.info(f"Bundling {len(bundled_ids)} tasks with Lead Task {lead_id} for resource {res_id}")
            final_goal += f"\n\n[SYSTEM] PARALLEL INTERRUPTS DETECTED: {bundled_ids}. " \
                          f"Please use 'get_task_details' to inspect all involved tasks and provide a consolidated solution."
            
            # Persist Relationship
            for sid in bundled_ids:
                execute_mutation("UPDATE tasks SET parent_interrupt_id = %s WHERE id = %s", (lead_id, sid), connection=connection)

        agent_url = handle['url']
        agent_id = handle['agent_id']
        
        # Atomically mark resource as busy and Lead Task as in_progress
        execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,), connection=connection)
        execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (lead_id,), connection=connection)
        
        logger.info(f"Dispatching Lead Task {lead_id} to {res_id} at {agent_url}. (Bundled: {bundled_ids})")
        
        threading.Thread(target=_trigger_agent_async, args=(agent_url, agent_id, lead_id, res_id, final_goal)).start()

def _trigger_agent_async(url: str, agent_id: str, task_id: str, res_id: str, goal: str):
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
        # Note: This runs outside the main bus transaction as it's in a thread.
        try:
            execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = %s", (task_id,))
            execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (res_id,))
        except: pass

def _watch_for_interrupts(connection=None):
    """
    Control Plane Watchdog: Identifies blocked/failed tasks and emits Interrupt Events.
    This awakens the Activity Manager (PM) to diagnose and heal the DAG.
    """
    try:
        # Fetch tasks that need intervention
        # We only care about root-level anomalies that haven't been resolved
        anomalies = execute_query("""
            SELECT t.id, t.activity_id, t.project_id, t.module_id, t.status, t.blocker_reason
            FROM tasks t
            WHERE t.status IN ('blocked', 'failed')
              AND t.id NOT LIKE 'INT-EVT-%'
        """, connection=connection)

        for task in anomalies:
            task_id = task['id']
            act_id = task['activity_id']
            proj_id = task['project_id']
            mod_id = task['module_id']
            status = task['status']
            reason = task['blocker_reason'] or "Unknown failure"
            
            # Generate unique interrupt ID (Version 1 for this task blockage)
            interrupt_id = f"INT-EVT-{task_id}"
            
            # Check if this specific interrupt was already fired
            existing = execute_query("SELECT id FROM tasks WHERE id = %s", (interrupt_id,), connection=connection)
            if existing:
                continue

            logger.warning(f"SYSTEM INTERRUPT: Task {task_id} is {status}. Awakening Control Plane.")

            goal = (f"INTERRUPT SIGNAL: Agent execution blocked at node {task_id}.\n"
                    f"Reason: {reason}\n"
                    f"Status: {status}\n\n"
                    "Your mission: As the Control Plane, analyze the activity state, diagnose why this node failed, "
                    "and use your DAG mutation tools to heal the system (e.g. rewrite task, split task, or reset state).")

            # Insert the Interrupt Task (Independent of DAG dependencies)
            sql = """
                INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                                   module_iteration_goal, estimated_hours, status)
                VALUES (%s, %s, %s, %s, 'RES-ARCHITECT-001', %s, 0.5, 'ready')
                ON CONFLICT (id) DO NOTHING
            """
            execute_mutation(sql, (interrupt_id, proj_id, act_id, mod_id, goal), connection=connection)
            logger.info(f"Interrupt Event {interrupt_id} successfully emitted to Bus.")

    except Exception as e:
        logger.error(f"Failed to emit interrupts: {e}")

def _reconcile_active_locks(connection=None):
    """
    Watchdog: Scans for physical lock files and reconciles them with the database.
    Releases locks for tasks that are no longer 'in_progress'.
    """
    try:
        # 1. Gather all directories to scan
        # We scan the root /app and any sub-workspaces
        scan_dirs = ["/app", "/app/workspaces"]
        
        # 2. Identify all physical locks
        locks_found = {} # Path -> Task ID
        for base in scan_dirs:
            if not os.path.isdir(base): continue
            for root, _, files in os.walk(base):
                if ".smart_task.lock" in files:
                    full_path = os.path.join(root, ".smart_task.lock")
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            task_id = f.read().strip()
                            locks_found[root] = task_id
                    except: pass

        if not locks_found:
            return

        # 3. Batch check statuses in DB
        task_ids = list(set(locks_found.values()))
        placeholders = ','.join(['%s']*len(task_ids))
        query = f"SELECT id, status FROM tasks WHERE id IN ({placeholders})"
        statuses = {t['id']: t['status'] for t in execute_query(query, tuple(task_ids), connection=connection)}

        # 4. Cleanup inconsistent locks
        for workspace_path, task_id in locks_found.items():
            db_status = statuses.get(task_id)
            
            # If task not in DB, or status is not 'in_progress' -> Release
            if not db_status or db_status != 'in_progress':
                logger.warning(f"Watchdog: Found stale lock for task {task_id} (Status: {db_status}) at {workspace_path}. Reclaiming.")
                _cleanup_task_resources(workspace_path, None, connection=connection) # res_id is None since we don't know it here
    except Exception as e:
        logger.error(f"Watchdog error: {e}")

def _cleanup_task_resources(workspace_path: str, resource_id: Optional[str], connection=None):
    """Releases locks and marks resource as available."""
    try:
        if workspace_path:
            workspace_lock_manager.unlock(workspace_path)
        
        if resource_id:
            execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (resource_id,), connection=connection)
            logger.info(f"Cleaned up resources for Agent {resource_id} and Workspace {workspace_path}")
    except Exception as e:
        logger.error(f"Cleanup error for resource {resource_id}: {e}")

def _monitor_activities(connection=None):
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
    stalled_activities = execute_query(query, connection=connection)
    
    for act in stalled_activities:
        act_id = act['id']
        project_id = act['project_id']
        root_module_id = act['root_module_id']
        rev_task_id = f"REV-{act_id}"
        
        # Check if intervention task already exists
        exist_check = execute_query("SELECT id FROM tasks WHERE id = %s", (rev_task_id,), connection=connection)
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
            execute_mutation(sql, (rev_task_id, project_id, act_id, root_module_id, goal), connection=connection)
            logger.info(f"Created intervention task {rev_task_id} for Activity Manager.")
        except Exception as e:
            logger.error(f"Failed to create intervention task for {act_id}: {e}")

def scheduler_daemon():
    """Background loop for continuous scheduling."""
    logger.info("Scheduler Daemon started.")
    while True:
        run_system_bus_cycle()
        time.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent_supervisor.load_config()
    scheduler_daemon()
