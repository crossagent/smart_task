import pytest
import uuid
import json
from src.task_management.db import execute_mutation, query_sql
from src.task_management.tools import upsert_resource, upsert_task
from src.task_execution.scheduler import run_scheduler_tick

@pytest.fixture
def resource_id():
    rid = f"RES-SCHED-{uuid.uuid4().hex[:8]}"
    upsert_resource(id=rid, name="Test Resource", org_role="Tester", resource_type="human", is_available=True)
    return rid

@pytest.fixture
def task_ids():
    return [f"TSK-SCHED-{uuid.uuid4().hex[:8]}" for _ in range(3)]

def test_scheduler_dag_transitions(resource_id, task_ids):
    """Test that the scheduler correctly evaluates depends_on constraints and advances task states."""
    # Insert a dummy module so we can hook tasks to it
    mod_id = f"MOD-SCHED-{uuid.uuid4().hex[:8]}"
    execute_mutation("INSERT INTO modules (id, name, owner_res_id) VALUES (%s, %s, %s)", (mod_id, "Test Module", resource_id))

    t1, t2, t3 = task_ids

    # Setup Tasks
    # T1: No dependencies
    upsert_task(id=t1, module_id=mod_id, module_name="Test Module", resource_id=resource_id, resource_name="Tester", module_iteration_goal="T1", status="pending")
    
    # T2: Depends on T1
    upsert_task(id=t2, module_id=mod_id, module_name="Test Module", resource_id=resource_id, resource_name="Tester", module_iteration_goal="T2", status="pending", depends_on='{"' + t1 + '"}')
    
    # T3: Depends on T2
    upsert_task(id=t3, module_id=mod_id, module_name="Test Module", resource_id=resource_id, resource_name="Tester", module_iteration_goal="T3", status="pending", depends_on='{"' + t2 + '"}')

    # Tick 1: T1 should go ready, others stay pending.
    run_scheduler_tick()

    res_t1 = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{t1}'"))[0]["status"]
    res_t2 = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{t2}'"))[0]["status"]
    assert res_t1 == "in_progress" # Because it was promoted to ready, and then instantly dispatched
    assert res_t2 == "pending"

    # Mark T1 as done manually
    execute_mutation("UPDATE tasks SET status = 'done' WHERE id = %s", (t1,))
    
    # Also we need to free the resource so T2 can be evaluated and dispatched
    execute_mutation("UPDATE resources SET is_available = True WHERE id = %s", (resource_id,))

    # Tick 2: T2 should go ready -> in_progress
    run_scheduler_tick()
    
    res_t2 = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{t2}'"))[0]["status"]
    res_t3 = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{t3}'"))[0]["status"]
    assert res_t2 == "in_progress"
    assert res_t3 == "pending"
