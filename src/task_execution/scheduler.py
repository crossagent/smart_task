from __future__ import annotations

import time
import json
import os
import logging
import httpx
import threading
from typing import Optional
from src.task_management.db import execute_query, execute_mutation, db_transaction
from src.resource_management.supervisor import agent_supervisor

logger = logging.getLogger("smart_task.task_execution.scheduler")


# ═══════════════════════════════════════════════════════════════
#  EVENT HANDLER REGISTRY
#  Each handler receives (event_row, connection) and returns
#  the task_id that will resolve this event (or None).
# ═══════════════════════════════════════════════════════════════

def _handle_task_anomaly(event, conn):
    """Handle task_blocked / task_failed events by creating a PM repair task."""
    task_id = event['task_id']
    act_id = event['activity_id']
    payload = event['payload'] if isinstance(event['payload'], dict) else json.loads(event['payload'])
    reason = payload.get('reason', 'Unknown failure')
    status = payload.get('original_status', 'failed')

    # Find context for the repair task
    ctx = execute_query(
        "SELECT project_id, module_id FROM tasks WHERE id = %s", (task_id,),
        connection=conn
    )
    if not ctx:
        logger.warning(f"Event {event['id']}: Referenced task {task_id} not found. Dismissing.")
        return None

    proj_id = ctx[0]['project_id']
    mod_id = ctx[0]['module_id']

    # Generate a unique repair task ID
    repair_task_id = f"REPAIR-{task_id}"
    
    goal = (f"INTERRUPT SIGNAL: Agent execution anomaly at node {task_id}.\n"
            f"Reason: {reason}\n"
            f"Status: {status}\n\n"
            "Your mission: As the Control Plane, analyze the activity state, diagnose why this node failed, "
            "and use your DAG mutation tools to heal the system (e.g. rewrite task, split task, or reset state).")

    sql = """
        INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                           module_iteration_goal, estimated_hours, status)
        VALUES (%s, %s, %s, %s, 'RES-ARCHITECT-001', %s, 0.5, 'ready')
        ON CONFLICT (id) DO NOTHING
    """
    execute_mutation(sql, (repair_task_id, proj_id, act_id, mod_id, goal), connection=conn)
    logger.info(f"Event {event['id']} → Created repair task {repair_task_id}")
    return repair_task_id


def _handle_human_instruction(event, conn):
    """Handle human_instruction events by creating a PM re-evaluation task."""
    act_id = event['activity_id']
    payload = event['payload'] if isinstance(event['payload'], dict) else json.loads(event['payload'])
    instruction = payload.get('instruction', 'No specific instruction provided.')
    version = payload.get('version', 0)

    # Find context
    ctx = execute_query(
        "SELECT project_id FROM activities WHERE id = %s", (act_id,),
        connection=conn
    )
    if not ctx:
        logger.warning(f"Event {event['id']}: Activity {act_id} not found. Dismissing.")
        return None

    proj_id = ctx[0]['project_id']
    cmd_task_id = f"CMD-{act_id}-V{version}"

    # Find a module_id from existing tasks in this activity
    mod_ctx = execute_query(
        "SELECT module_id FROM tasks WHERE activity_id = %s LIMIT 1", (act_id,),
        connection=conn
    )
    if not mod_ctx:
        logger.warning(f"Event {event['id']}: No tasks found for activity {act_id}. Dismissing.")
        return None

    mod_id = mod_ctx[0]['module_id']

    goal = (f"HUMAN COMMAND RECEIVED (Version {version}):\n\n"
            f"\"{instruction}\"\n\n"
            "As the Control Plane, you must now re-evaluate your current DAG plan. "
            "Use your tools to adjust task goals, add new nodes, or reset states to satisfy the user's new requirements.")

    sql = """
        INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                           module_iteration_goal, estimated_hours, status)
        VALUES (%s, %s, %s, %s, 'RES-ARCHITECT-001', %s, 0.5, 'ready')
        ON CONFLICT (id) DO NOTHING
    """
    execute_mutation(sql, (cmd_task_id, proj_id, act_id, mod_id, goal), connection=conn)
    logger.info(f"Event {event['id']} → Created command task {cmd_task_id}")
    return cmd_task_id


def _handle_activity_stalled(event, conn):
    """Handle activity_stalled events by creating a review task for the PM."""
    act_id = event['activity_id']
    payload = event['payload'] if isinstance(event['payload'], dict) else json.loads(event['payload'])
    completed = payload.get('completed', 0)
    total = payload.get('total', 0)
    issues = payload.get('issues', 0)

    ctx = execute_query(
        "SELECT project_id FROM activities WHERE id = %s", (act_id,),
        connection=conn
    )
    if not ctx:
        return None

    proj_id = ctx[0]['project_id']
    rev_task_id = f"REV-{act_id}"

    # Find root module
    mod_ctx = execute_query("""
        SELECT m.id FROM tasks t
        JOIN modules m ON t.module_id = m.id AND m.parent_module_id IS NULL
        WHERE t.activity_id = %s LIMIT 1
    """, (act_id,), connection=conn)
    if not mod_ctx:
        return None

    mod_id = mod_ctx[0]['id']

    goal = (f"Review Activity {act_id}. All subtasks are terminal. "
            f"Completed: {completed}/{total}. Issues: {issues}. "
            "Analyze the execution results and either officially close the Activity or break down new tasks to fix issues.")

    sql = """
        INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                           module_iteration_goal, estimated_hours, status)
        VALUES (%s, %s, %s, %s, 'RES-ARCHITECT-001', %s, 1.0, 'ready')
        ON CONFLICT (id) DO NOTHING
    """
    execute_mutation(sql, (rev_task_id, proj_id, act_id, mod_id, goal), connection=conn)
    logger.info(f"Event {event['id']} → Created review task {rev_task_id}")
    return rev_task_id


# Handler routing table
EVENT_HANDLERS = {
    'task_blocked':        _handle_task_anomaly,
    'task_failed':         _handle_task_anomaly,
    'human_instruction':   _handle_human_instruction,
    'activity_stalled':    _handle_activity_stalled,
}


# ═══════════════════════════════════════════════════════════════
#  CORE BUS CYCLE
# ═══════════════════════════════════════════════════════════════

def run_system_bus_cycle():
    """
    Core System Control Bus Cycle (Event-Driven).
    
    Phase 1: DETECT   — Scan for anomalies, write events
    Phase 2: CONSUME  — Read pending events, route to handlers → Task mutations
    Phase 3: EXECUTE  — Promote & Dispatch tasks (gated by run_mode)
    Phase 4: RECONCILE — Release completed task resources
    """
    try:
        with db_transaction() as conn:
            # ═══ Phase 1: EVENT DETECTION (Sensors) ═══
            _detect_task_anomalies(connection=conn)
            _detect_human_interventions(connection=conn)
            _detect_stalled_activities(connection=conn)

            # ═══ Phase 2: EVENT CONSUMPTION (Control Plane) ═══
            _process_pending_events(connection=conn)

            # ═══ Phase 3: CONTROL GATE + DATA PLANE ═══
            state_data = execute_query("SELECT key, value FROM system_state", connection=conn)
            state = {row['key']: row['value'] for row in state_data}
            
            run_mode = state.get('run_mode', "auto")
            if isinstance(run_mode, str):
                run_mode = run_mode.strip('"') 
            
            step_count = int(state.get('step_count', 0))

            if run_mode == "pause" and step_count <= 0:
                logger.debug("System Bus Cycle: GATED/PAUSED. Skipping execution logic.")
            else:
                if step_count > 0:
                    logger.info(f"System Bus Cycle: STEP mode ({step_count} remaining). Executing...")
                    execute_mutation("UPDATE system_state SET value = %s WHERE key = 'step_count'", (str(step_count - 1),), connection=conn)

                # Data Plane flow
                _promote_pending_tasks(connection=conn)
                _dispatch_ready_tasks(connection=conn)

            # ═══ Phase 4: RECONCILE ═══
            _reconcile_completed_tasks(connection=conn)
                
    except Exception as e:
        logger.error(f"Error in system bus cycle: {e}")


# ═══════════════════════════════════════════════════════════════
#  PHASE 1: EVENT DETECTION (Sensors)
#  Each detector scans for a specific condition and emits
#  structured events into the events table. No Task mutation here.
# ═══════════════════════════════════════════════════════════════

def _detect_task_anomalies(connection=None):
    """Scan for blocked/failed tasks and emit events."""
    try:
        anomalies = execute_query("""
            SELECT t.id, t.activity_id, t.project_id, t.module_id, t.status, t.blocker_reason
            FROM tasks t
            WHERE t.status IN ('blocked', 'failed')
        """, connection=connection)

        for task in anomalies:
            event_type = 'task_blocked' if task['status'] == 'blocked' else 'task_failed'
            payload = json.dumps({
                'reason': task['blocker_reason'] or 'Unknown failure',
                'original_status': task['status'],
                'module_id': task['module_id']
            })
            
            # INSERT with dedup index — duplicate pending events for same task_id are silently ignored
            execute_mutation("""
                INSERT INTO events (event_type, source, severity, activity_id, task_id, resource_id, payload)
                VALUES (%s, 'scheduler', 'warning', %s, %s, NULL, %s)
                ON CONFLICT DO NOTHING
            """, (event_type, task['activity_id'], task['id'], payload), connection=connection)

    except Exception as e:
        logger.error(f"Event detection (task anomalies) failed: {e}")


def _detect_human_interventions(connection=None):
    """Detect user instruction updates and emit events."""
    try:
        updated_activities = execute_query("""
            SELECT a.id, a.project_id, a.user_instruction, a.instruction_version
            FROM activities a
            LEFT JOIN system_state s ON s.key = 'last_human_evt_' || a.id
            WHERE a.status = 'Active' 
              AND a.instruction_version > COALESCE((s.value->>0)::int, -1)
        """, connection=connection)

        for act in updated_activities:
            act_id = act['id']
            version = act['instruction_version']
            instruction = act['user_instruction'] or "No specific instruction provided."

            logger.warning(f"HUMAN INTERVENTION: User updated instructions for Activity {act_id} (v{version}).")

            payload = json.dumps({
                'instruction': instruction,
                'version': version
            })

            execute_mutation("""
                INSERT INTO events (event_type, source, severity, activity_id, payload)
                VALUES ('human_instruction', 'human', 'critical', %s, %s)
            """, (act_id, payload), connection=connection)

            # Record that we've processed this version
            execute_mutation("""
                INSERT INTO system_state (key, value) 
                VALUES ('last_human_evt_' || %s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (act_id, str(version)), connection=connection)

    except Exception as e:
        logger.error(f"Event detection (human interventions) failed: {e}")


def _detect_stalled_activities(connection=None):
    """Detect activities where all tasks have reached terminal state."""
    try:
        query = """
            SELECT a.id, a.project_id,
                   COUNT(t.id) as total_tasks,
                   COUNT(CASE WHEN t.status IN ('done', 'code_done') THEN 1 END) as completed,
                   COUNT(CASE WHEN t.status IN ('failed', 'blocked') THEN 1 END) as issues,
                   COUNT(CASE WHEN t.status IN ('pending', 'ready', 'in_progress', 'needs_human_help') THEN 1 END) as active
            FROM activities a
            JOIN tasks t ON a.id = t.activity_id
            WHERE a.status = 'Active'
            GROUP BY a.id, a.project_id
            HAVING COUNT(CASE WHEN t.status IN ('pending', 'ready', 'in_progress', 'needs_human_help') THEN 1 END) = 0
        """
        stalled = execute_query(query, connection=connection)

        for act in stalled:
            payload = json.dumps({
                'completed': act['completed'],
                'total': act['total_tasks'],
                'issues': act['issues']
            })

            # Use activity_id as task_id for dedup (one stall event per activity)
            execute_mutation("""
                INSERT INTO events (event_type, source, severity, activity_id, task_id, payload)
                VALUES ('activity_stalled', 'scheduler', 'normal', %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (act['id'], f"stall-{act['id']}", payload), connection=connection)

    except Exception as e:
        logger.error(f"Event detection (stalled activities) failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  PHASE 2: EVENT CONSUMPTION
#  Reads pending events ordered by severity, routes to handlers.
# ═══════════════════════════════════════════════════════════════

def _process_pending_events(connection=None):
    """Consume pending events and translate them into task-level actions."""
    try:
        events = execute_query("""
            SELECT * FROM events 
            WHERE status = 'pending' 
            ORDER BY 
                CASE severity 
                    WHEN 'critical' THEN 0 
                    WHEN 'warning' THEN 1 
                    ELSE 2 
                END,
                created_at ASC
        """, connection=connection)

        for event in events:
            handler = EVENT_HANDLERS.get(event['event_type'])
            if handler:
                try:
                    result_task_id = handler(event, connection)
                    if result_task_id:
                        execute_mutation("""
                            UPDATE events 
                            SET status = 'processing', resolved_by = %s 
                            WHERE id = %s
                        """, (result_task_id, event['id']), connection=connection)
                        logger.info(f"Event #{event['id']} ({event['event_type']}) → routed to {result_task_id}")
                    else:
                        # Handler returned None — dismiss the event
                        execute_mutation("""
                            UPDATE events 
                            SET status = 'dismissed', resolved_at = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (event['id'],), connection=connection)
                        logger.info(f"Event #{event['id']} ({event['event_type']}) → dismissed (no action needed)")
                except Exception as e:
                    logger.error(f"Handler failed for event #{event['id']}: {e}")
            else:
                logger.warning(f"No handler registered for event type: {event['event_type']}")

    except Exception as e:
        logger.error(f"Event consumption failed: {e}")


# ═══════════════════════════════════════════════════════════════
#  PHASE 3: DATA PLANE (Promote + Dispatch)
# ═══════════════════════════════════════════════════════════════

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

    # 3. Dispatch Grouped (Single Trigger per Agent)
    for res_id, tasks in tasks_by_res.items():
        # Check if the agent is actually up in the pool
        handle = agent_supervisor.pool.get(res_id)
        if not handle:
            logger.warning(f"Task {tasks[0]['task_id']} deferred: Resource {res_id} not found in persistent pool.")
            continue
            
        # Pick the most recent task to trigger the agent
        lead = tasks[0]
        lead_id = lead['task_id']
        final_goal = lead['module_iteration_goal']
        
        # Note: We send just one task, the PM is instructed to scan for all others
        agent_url = handle['url']
        agent_id = handle['agent_id']
        
        # Mark as busy and dispatch
        execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (res_id,), connection=connection)
        execute_mutation("UPDATE tasks SET status = 'in_progress' WHERE id = %s", (lead_id,), connection=connection)
        
        logger.info(f"Dispatching wake-up task {lead_id} to Resource {res_id}. Agent is expected to scan for other {len(tasks)-1} pending tasks.")
        
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


# ═══════════════════════════════════════════════════════════════
#  PHASE 4: RECONCILE
# ═══════════════════════════════════════════════════════════════

def _reconcile_completed_tasks(connection=None):
    """Checks for tasks that finished execution and releases their resource/locks."""
    completed_tasks = execute_query("""
        SELECT t.id, t.resource_id, r.workspace_path
        FROM tasks t
        JOIN resources r ON t.resource_id = r.id
        WHERE t.status IN ('done', 'code_done', 'failed') AND r.is_available = False
    """, connection=connection)
    
    for task in completed_tasks:
        task_id = task['id']
        res_id = task['resource_id']
        
        logger.info(f"Reconciling completed task {task_id}. Releasing resource {res_id}.")
        _cleanup_task_resources(res_id, connection=connection)

        # Also resolve any events that were linked to this task
        execute_mutation("""
            UPDATE events 
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP 
            WHERE resolved_by = %s AND status = 'processing'
        """, (task_id,), connection=connection)


def _cleanup_task_resources(resource_id: Optional[str], connection=None):
    """Marks resource as available."""
    try:
        if resource_id:
            execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (resource_id,), connection=connection)
            logger.info(f"Released resource {resource_id}")
    except Exception as e:
        logger.error(f"Cleanup error for resource {resource_id}: {e}")


# ═══════════════════════════════════════════════════════════════
#  DAEMON
# ═══════════════════════════════════════════════════════════════

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
