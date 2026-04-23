from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List
from .db import execute_query, execute_mutation
import json

router = APIRouter(prefix="/api")

@router.get("/activities")
async def get_activities(
    start: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end: Optional[str] = Query(None, description="End date (YYYY-MM-DD)")
):
    """List activities with optional date filtering."""
    sql = "SELECT id, name, status, priority, created_at FROM activities"
    params = []
    
    where_clauses = []
    if start:
        where_clauses.append("created_at >= %s")
        params.append(start)
    if end:
        where_clauses.append("created_at <= %s")
        params.append(end)
        
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    sql += " ORDER BY created_at DESC"
    
    try:
        results = execute_query(sql, tuple(params))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity/{activity_id}/graph")
async def get_activity_graph(activity_id: str):
    """Returns task nodes and edges for Mermaid visualization."""
    sql = """
        SELECT id, module_id, resource_id, module_iteration_goal, status, is_approved, depends_on
        FROM tasks
        WHERE activity_id = %s
    """
    try:
        tasks = execute_query(sql, (activity_id,))
        if not tasks:
            return {"nodes": [], "edges": []}
            
        nodes = []
        edges = []
        
        for t in tasks:
            # Node metadata
            nodes.append({
                "id": t['id'],
                "label": f"{t['id']}\n({t['module_id']})",
                "status": t['status'],
                "is_approved": t['is_approved'],
                "goal": t['module_iteration_goal']
            })
            
            # Edges from depends_on
            deps = t['depends_on'] or []
            for dep_id in deps:
                edges.append({"from": dep_id, "to": t['id']})
                
        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/activity/{activity_id}/details")
async def get_activity_details(activity_id: str):
    """Aggregated stats and metadata for the activity."""
    act_sql = "SELECT * FROM activities WHERE id = %s"
    prog_sql = "SELECT * FROM v_activity_progress WHERE activity_id = %s"
    
    try:
        act = execute_query(act_sql, (activity_id,))
        prog = execute_query(prog_sql, (activity_id,))
        
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")
            
        return {
            "metadata": act[0],
            "progress": prog[0] if prog else {"completion_percentage": 0}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}/logs")
async def get_logs(task_id: str):
    """Retrieve execution logs for a specific task."""
    from src.task_management.tools import get_task_logs
    try:
        logs = get_task_logs(task_id)
        return {"logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/task/{task_id}/approve")
async def approve(task_id: str):
    """Manually approve a task and promote it to READY."""
    from .tools import approve_task
    try:
        result = approve_task(task_id)
        return {"message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/task/{task_id}/block")
async def block_task(task_id: str, reason: str = Query("External Block")):
    """Forcefully marks a task as blocked."""
    sql = "UPDATE tasks SET status = 'blocked', blocker_reason = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    try:
        execute_mutation(sql, (reason, task_id))
        return {"status": "success", "message": f"Task {task_id} blocked."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SYSTEM COCKPIT CONTROLS ---

@router.get("/system/status")
async def get_system_status():
    """Returns the current run mode and step status."""
    try:
        data = execute_query("SELECT key, value FROM system_state")
        return {row['key']: row['value'] for row in data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/system/control")
async def set_system_control(mode: str = Query(None), step: int = Query(0)):
    """Updates global system mode or adds step tokens."""
    try:
        if mode:
            execute_mutation("UPDATE system_state SET value = %s WHERE key = 'run_mode'", (json.dumps(mode),))
        if step > 0:
            execute_mutation("UPDATE system_state SET value = (COALESCE(value::int, 0) + %s)::text::jsonb WHERE key = 'step_count'", (step,))
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/activity/{activity_id}/instruction")
async def update_activity_instruction(activity_id: str, instruction: str):
    """Updates user instruction and bumps version and triggers PM via event."""
    sql = """
        UPDATE activities 
        SET user_instruction = %s, 
            instruction_version = instruction_version + 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        RETURNING instruction_version
    """
    try:
        # Use execute_query to get the RETURNING value
        result = execute_query(sql, (instruction, activity_id))
        version = result[0]['instruction_version'] if result else 0
        
        # Emit event directly (human-initiated)
        payload = json.dumps({'instruction': instruction, 'version': version})
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, payload)
            VALUES ('human_instruction', 'human', 'critical', %s, %s)
        """, (activity_id, payload))
        
        # Record version so scheduler doesn't double-detect
        execute_mutation("""
            INSERT INTO system_state (key, value) 
            VALUES ('last_human_evt_' || %s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (activity_id, str(version)))
        
        return {"status": "success", "version": version}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- EVENT TIMELINE API ---

@router.get("/events")
async def get_events(
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, resolved, dismissed"),
    activity_id: Optional[str] = Query(None, description="Filter by activity"),
    limit: int = Query(50, description="Max results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Returns the event timeline for the dashboard."""
    sql = "SELECT * FROM events"
    params = []
    where_clauses = []

    if status:
        where_clauses.append("status = %s")
        params.append(status)
    if activity_id:
        where_clauses.append("activity_id = %s")
        params.append(activity_id)
    
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    try:
        results = execute_query(sql, tuple(params))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events")
async def create_event(
    event_type: str,
    severity: str = Query("normal"),
    activity_id: Optional[str] = Query(None),
    task_id: Optional[str] = Query(None),
    payload: str = Query("{}")
):
    """Human-initiated event creation from the dashboard."""
    try:
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, task_id, payload)
            VALUES (%s, 'human', %s, %s, %s, %s)
        """, (event_type, severity, activity_id, task_id, payload))
        return {"status": "success", "message": f"Event '{event_type}' created."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{event_id}/dismiss")
async def dismiss_event(event_id: int):
    """Dismiss (ignore) a pending event."""
    try:
        count = execute_mutation("""
            UPDATE events 
            SET status = 'dismissed', resolved_by = 'human', resolved_at = CURRENT_TIMESTAMP 
            WHERE id = %s AND status = 'pending'
        """, (event_id,))
        if count == 0:
            raise HTTPException(status_code=404, detail="Event not found or already processed")
        return {"status": "success", "message": f"Event #{event_id} dismissed."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

