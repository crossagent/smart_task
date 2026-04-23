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
#  EVENT RESOLVERS (The "Attention Core" Logic)
# ==============================================================================

def _call_attention_core_agent(event_type: str, context: dict) -> List[dict]:
    """
    Conceptual interface to the Architect Agent (Attention Core).
    In production, this triggers an LLM call to rebuild the blueprint.
    Returns a list of blueprint operations.
    """
    # This is mocked in tests to simulate agent decisions.
    # Default behavior: identity (do nothing)
    return []

def _execute_blueprint_actions(actions: List[dict], conn):
    """Executes a list of atomic blueprint modifications decided by the Agent."""
    for action in actions:
        op = action.get('op')
        table = action.get('table')
        data = action.get('data', {})
        where = action.get('where', {})

        if op == 'update':
            cols = ", ".join([f"{k} = %s" for k in data.keys()])
            conds = " AND ".join([f"{k} = %s" for k in where.keys()])
            sql = f"UPDATE {table} SET {cols} WHERE {conds}"
            execute_mutation(sql, list(data.values()) + list(where.values()), connection=conn)
        
        elif op == 'insert':
            cols = ", ".join(data.keys())
            placeholders = ", ".join(["%s"] * len(data))
            sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
            execute_mutation(sql, list(data.values()), connection=conn)
            
        elif op == 'delete':
            conds = " AND ".join([f"{k} = %s" for k in where.keys()])
            sql = f"DELETE FROM {table} WHERE {conds}"
            execute_mutation(sql, list(where.values()), connection=conn)

def _resolve_event_generic(event, conn):
    """Generic resolver that bridges the Event to the Agent's blueprint reconstruction."""
    event_type = event['event_type']
    payload = event['payload'] if isinstance(event['payload'], dict) else json.loads(event['payload'])
    
    # 1. Get Decision from Attention Core Agent
    actions = _call_attention_core_agent(event_type, payload)
    
    # 2. Apply all blueprint modifications atomically
    _execute_blueprint_actions(actions, conn)
    
    logger.info(f"Attention Core: Executed {len(actions)} blueprint actions for {event_type}.")
    return True

EVENT_RESOLVERS = {
    'task_blocked': _resolve_event_generic,
    'task_failed': _resolve_event_generic,
    'human_instruction': _resolve_event_generic,
    'activity_stalled': _resolve_event_generic,
}

# ==============================================================================
#  CORE BUS CYCLE
# ==============================================================================

def run_system_bus_cycle():
    try:
        with db_transaction() as conn:
            # 1. SCAN (Passive detection)
            _detect_task_anomalies(connection=conn)
            _detect_human_interventions(connection=conn)
            _detect_stalled_activities(connection=conn)

            # 2. RESOLVE (Active Attention - Direct Blueprint Modification)
            _process_pending_events(connection=conn)

            # 3. SCHEDULE (Data Plane Promotion)
            state_data = execute_query("SELECT key, value FROM system_state", connection=conn)
            state = {row['key']: row['value'] for row in state_data}
            run_mode = str(state.get('run_mode', "auto")).strip('"')
            step_count = int(state.get('step_count', 0))

            if run_mode != "pause" or step_count > 0:
                if step_count > 0:
                    execute_mutation("UPDATE system_state SET value = %s WHERE key = 'step_count'", (str(step_count - 1),), connection=conn)
                
                _promote_pending_tasks(connection=conn)
                _dispatch_ready_tasks(connection=conn)

            # 4. RECONCILE (Cleanup)
            _reconcile_completed_tasks(connection=conn)
    except Exception as e:
        logger.error(f"System Bus Cycle Error: {e}")

def _detect_task_anomalies(connection=None):
    # Same as before...
    anomalies = execute_query("SELECT id, activity_id, project_id, module_id, status, blocker_reason FROM tasks WHERE status IN ('blocked', 'failed')", connection=connection)
    for task in anomalies:
        event_type = 'task_blocked' if task['status'] == 'blocked' else 'task_failed'
        payload = json.dumps({'reason': task['blocker_reason'], 'module_id': task['module_id']})
        execute_mutation("INSERT INTO events (event_type, source, severity, activity_id, task_id, payload) VALUES (%s, 'scheduler', 'warning', %s, %s, %s) ON CONFLICT DO NOTHING", (event_type, task['activity_id'], task['id'], payload), connection=connection)

def _detect_human_interventions(connection=None):
    # Same as before...
    updated = execute_query("SELECT a.id, a.user_instruction, a.instruction_version FROM activities a LEFT JOIN system_state s ON s.key = 'last_human_evt_' || a.id WHERE a.status = 'Active' AND a.instruction_version > COALESCE((s.value->>0)::int, -1)", connection=connection)
    for act in updated:
        payload = json.dumps({'instruction': act['user_instruction'], 'version': act['instruction_version']})
        execute_mutation("INSERT INTO events (event_type, source, severity, activity_id, payload) VALUES ('human_instruction', 'human', 'critical', %s, %s)", (act['id'], payload), connection=connection)
        execute_mutation("INSERT INTO system_state (key, value) VALUES ('last_human_evt_' || %s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (act['id'], str(act['instruction_version'])), connection=connection)

def _detect_stalled_activities(connection=None):
    # Same as before...
    query = """
        SELECT a.id, COUNT(t.id) as total, COUNT(CASE WHEN t.status IN ('done', 'failed', 'blocked') THEN 1 END) as terminal
        FROM activities a JOIN tasks t ON a.id = t.activity_id
        WHERE a.status = 'Active' GROUP BY a.id HAVING COUNT(CASE WHEN t.status NOT IN ('done', 'failed', 'blocked') THEN 1 END) = 0
    """
    for act in execute_query(query, connection=connection):
        execute_mutation("INSERT INTO events (event_type, source, activity_id, task_id) VALUES ('activity_stalled', 'scheduler', %s, %s) ON CONFLICT DO NOTHING", (act['id'], f"stall-{act['id']}"), connection=connection)

def _process_pending_events(connection=None):
    events = execute_query("SELECT * FROM events WHERE status = 'pending' ORDER BY severity DESC, created_at ASC", connection=connection)
    for event in events:
        resolver = EVENT_RESOLVERS.get(event['event_type'])
        if resolver:
            # The RESOLVER directly modifies the blueprint
            resolution_id = resolver(event, connection)
            status = 'resolved' if resolution_id else 'dismissed'
            execute_mutation("UPDATE events SET status = %s, resolved_by = %s, resolved_at = now() WHERE id = %s", (status, resolution_id, event['id']), connection=connection)

def _promote_pending_tasks(connection=None):
    pending = execute_query("SELECT id, depends_on, is_approved FROM tasks WHERE status = 'pending'", connection=connection)
    for task in pending:
        task_id = task['id']
        deps = task['depends_on'] or []
        can_promote = False
        if not deps:
            can_promote = True
        else:
            placeholders = ','.join(['%s']*len(deps))
            dep_rows = execute_query(f"SELECT status FROM tasks WHERE id IN ({placeholders})", tuple(deps), connection=connection)
            can_promote = len(dep_rows) == len(deps) and all(d['status'] in ('done', 'failed') for d in dep_rows)

        if can_promote:
            status = 'ready' if task['is_approved'] else 'awaiting_approval'
            execute_mutation("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id), connection=connection)

def _dispatch_ready_tasks(connection=None):
    """Pure Worker Dispatch. Management tasks are handled by the Attention Core."""
    ready_tasks = execute_query("SELECT t.id, t.module_id, t.module_iteration_goal, m.owner_res_id FROM tasks t JOIN modules m ON t.module_id = m.id WHERE t.status = 'ready' ORDER BY t.id", connection=connection)
    available_resources = execute_query("SELECT id FROM resources WHERE is_available = True AND org_role != 'Control Plane' ORDER BY id", connection=connection)
    
    if not ready_tasks or not available_resources: return

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
            threading.Thread(target=_trigger_agent_async, args=(handle['url'], handle['agent_id'], task['id'], candidate, task['module_iteration_goal'])).start()

def _trigger_agent_async(url: str, agent_id: str, task_id: str, res_id: str, goal: str):
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{url}/run", json={"app_name": agent_id, "session_id": task_id, "new_message": {"parts": [{"text": goal}]}})
    except Exception as e:
        logger.error(f"Trigger failed for {task_id}: {e}")

def _reconcile_completed_tasks(connection=None):
    active_assignments = execute_query("SELECT a.id as assign_id, a.task_id, a.resource_id, t.status as task_status FROM task_assignments a JOIN tasks t ON a.task_id = t.id WHERE a.status = 'active'", connection=connection)
    for assign in active_assignments:
        if assign['task_status'] in ('done', 'failed', 'blocked'):
            execute_mutation("UPDATE task_assignments SET status = 'completed', completed_at = now() WHERE id = %s", (assign['assign_id'],), connection=connection)
            execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (assign['resource_id'],), connection=connection)

def scheduler_daemon():
    logger.info("Scheduler Daemon started (Attention Core Mode).")
    while True:
        run_system_bus_cycle()
        time.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent_supervisor.load_config()
    scheduler_daemon()
