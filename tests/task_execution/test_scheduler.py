import pytest
import uuid
import json
from src.task_management.db import execute_mutation, query_sql
from src.task_management.tools import upsert_resource, upsert_task
from src.task_execution.scheduler import (
    run_scheduler_tick, 
    run_agent_subprocess
)
from unittest.mock import patch, MagicMock

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

def test_scheduler_dag_blocking_dependency(resource_id):
    """Verify that a task remains pending if its dependency is NOT 'done'."""
    mod_id = f"MOD-BLOCK-{uuid.uuid4().hex[:8]}"
    execute_mutation("INSERT INTO modules (id, name, owner_res_id) VALUES (%s, %s, %s)", (mod_id, "Block Mod", resource_id))

    t_parent = f"TSK-PARENT-{uuid.uuid4().hex[:8]}"
    t_child = f"TSK-CHILD-{uuid.uuid4().hex[:8]}"
    
    # Parent is in_progress
    upsert_task(id=t_parent, module_id=mod_id, module_name="M", resource_id=resource_id, resource_name="R", status="in_progress")
    # Child depends on Parent
    upsert_task(id=t_child, module_id=mod_id, module_name="M", resource_id=resource_id, resource_name="R", status="pending", depends_on='{"' + t_parent + '"}')

    run_scheduler_tick()
    
    res_child = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{t_child}'"))[0]["status"]
    assert res_child == "pending"

@patch("subprocess.Popen")
def test_scheduler_dispatch_subprocess_mapping(mock_popen, resource_id):
    """Verify that the scheduler sets correct env vars and calls the right command."""
    mod_id = f"MOD-DISPATCH-{uuid.uuid4().hex[:8]}"
    execute_mutation("INSERT INTO modules (id, name, owner_res_id) VALUES (%s, %s, %s)", (mod_id, "Dispatch Mod", resource_id))
    
    # Update resource with an agent_dir
    agent_dir = "smart_task_app/agents/test_agent"
    workspace = "d:/temp/workspace"
    execute_mutation("UPDATE resources SET agent_dir = %s, workspace_path = %s WHERE id = %s", (agent_dir, workspace, resource_id))

    task_id = f"TSK-DISPATCH-{uuid.uuid4().hex[:8]}"
    upsert_task(id=task_id, module_id=mod_id, module_name="M", resource_id=resource_id, resource_name="R", status="ready")

    # Mock process behavior
    mock_proc = MagicMock()
    mock_proc.stdout = []
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc

    # Trigger dispatch
    run_scheduler_tick()
    
    # Wait a tiny bit for the thread to start and call Popen
    import time
    time.sleep(0.5)
    
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd == ["uv", "run", "adk", "run", agent_dir]
    
    env = kwargs["env"]
    assert env["SMART_TASK_ID"] == task_id
    assert env["SMART_WORKSPACE_PATH"] == workspace

@patch("subprocess.Popen")
def test_scheduler_subprocess_status_callback(mock_popen, resource_id):
    """Verify that the scheduler updates task status based on process exit code."""
    mod_id = f"MOD-CALLBACK-{uuid.uuid4().hex[:8]}"
    execute_mutation("INSERT INTO modules (id, name, owner_res_id) VALUES (%s, %s, %s)", (mod_id, "Callback Mod", resource_id))

    task_success = f"TSK-SUCCESS-{uuid.uuid4().hex[:8]}"
    task_fail = f"TSK-FAIL-{uuid.uuid4().hex[:8]}"

    # 1. Test Success
    upsert_task(id=task_success, module_id=mod_id, module_name="M", resource_id=resource_id, resource_name="R", status="ready")
    
    mock_proc_success = MagicMock()
    mock_proc_success.stdout = []
    mock_proc_success.returncode = 0
    mock_popen.return_value = mock_proc_success

    # Since run_scheduler_tick starts a thread, we'll call run_agent_subprocess directly for deterministic test
    # (or we could use time.sleep, but direct call is cleaner for logic verification)
    run_agent_subprocess(task_success, resource_id, "some/dir", "some/path")
    
    status_success = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{task_success}'"))[0]["status"]
    assert status_success == "code_done"

    # 2. Test Failure
    upsert_task(id=task_fail, module_id=mod_id, module_name="M", resource_id=resource_id, resource_name="R", status="ready")
    
    mock_proc_fail = MagicMock()
    mock_proc_fail.stdout = []
    mock_proc_fail.returncode = 1
    mock_popen.return_value = mock_proc_fail
    
    # Reset resource to available before calling (simulating scheduler dispatch logic)
    execute_mutation("UPDATE resources SET is_available = False WHERE id = %s", (resource_id,))
    run_agent_subprocess(task_fail, resource_id, "some/dir", "some/path")
    
    status_fail = json.loads(query_sql(f"SELECT status FROM tasks WHERE id = '{task_fail}'"))[0]["status"]
    assert status_fail == "failed"
    
    # Also verify resource was freed
    res_available = json.loads(query_sql(f"SELECT is_available FROM resources WHERE id = '{resource_id}'"))[0]["is_available"]
    assert res_available is True
