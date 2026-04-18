import pytest
import respx
import httpx
from unittest.mock import MagicMock, patch, ANY
# Import the actual core cycle
from src.task_execution.scheduler import run_system_bus_cycle as run_scheduler_tick
from src.resource_management.supervisor import agent_supervisor
from src.task_management.db import execute_query, execute_mutation

@pytest.fixture(autouse=True)
def db_setup_cleanup(db_conn):
    """Ensure the database is clean before and after tests."""
    # 1. Clean up potential leftover data
    execute_mutation("DELETE FROM system_state")
    execute_mutation("DELETE FROM tasks")
    execute_mutation("DELETE FROM modules")
    execute_mutation("DELETE FROM activities")
    execute_mutation("DELETE FROM projects")
    execute_mutation("DELETE FROM resources")
    
    # 2. Seed system state
    execute_mutation("INSERT INTO system_state (key, value) VALUES ('run_mode', '\"auto\"')")
    execute_mutation("INSERT INTO system_state (key, value) VALUES ('step_count', '0')")
    
    yield
    
    # 3. Cleanup after test
    execute_mutation("DELETE FROM system_state")
    execute_mutation("DELETE FROM tasks")
    execute_mutation("DELETE FROM modules")
    execute_mutation("DELETE FROM activities")
    execute_mutation("DELETE FROM projects")
    execute_mutation("DELETE FROM resources")

@respx.mock
def test_full_pool_dispatch_and_reconcile():
    """
    INTEGRATION TEST: Verifies the full scheduler bus cycle using a REAL database.
    Flow: Ready Task -> Dispatch -> Busy Resource -> Task Done -> Reconcile -> Available Resource.
    """
    
    # 1. SEED DATA into Real Database
    # -----------------------------
    # Create Resource
    execute_mutation("""
        INSERT INTO resources (id, name, org_role, workspace_path, is_available)
        VALUES ('R1', 'Test Agent R1', 'Coder', '/work/w1', True),
               ('RES-ARCHITECT-001', 'System Architect', 'Control Plane', '/app', True)
    """)
    
    # Create Project
    execute_mutation("""
        INSERT INTO projects (id, name, initiator_res_id, memo_content)
        VALUES ('P1', 'Test Project', 'R1', 'Test Memo')
    """)
    
    # Create Activity
    execute_mutation("""
        INSERT INTO activities (id, name, project_id, owner_res_id)
        VALUES ('A1', 'Test Activity', 'P1', 'R1')
    """)
    
    # Create Module
    execute_mutation("""
        INSERT INTO modules (id, name, owner_res_id)
        VALUES ('M1', 'Test Module', 'R1')
    """)
    
    # Create Task (Ready for dispatch)
    execute_mutation("""
        INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, module_iteration_goal, status)
        VALUES ('T1', 'P1', 'A1', 'M1', 'R1', 'Build a feature', 'ready')
    """)

    # 2. Configure Agent Supervisor Pool
    # ---------------------------------
    agent_supervisor.pool = {
        "R1": {"url": "http://agent-r1:9001", "agent_id": "r1-agent"}
    }

    # 3. Mock Agent Network IO
    # -----------------------
    # Mock Session Init
    session_route = respx.post("http://agent-r1:9001/apps/r1-agent/users/smart-task-scheduler/sessions").respond(201, json={"status": "created"})
    # Mock /run endpoint
    agent_route = respx.post("http://agent-r1:9001/run").respond(200, json={"status": "accepted"})
    
    # 4. First tick: Dispatch Logic
    # ----------------------------
    # Mock threading.Thread to run target synchronously for deterministic testing
    with patch("src.task_execution.scheduler.threading.Thread") as mock_thread:
        def sync_run(target, args=(), kwargs={}, daemon=True):
            target(*args, **kwargs)
            return MagicMock()
        mock_thread.side_effect = sync_run
        
        # ACT: First Cycle
        run_scheduler_tick()
    
    # VERIFY: Database state after dispatch
    task_res = execute_query("SELECT status FROM tasks WHERE id = 'T1'")
    assert task_res[0]['status'] == 'in_progress'
    
    res_res = execute_query("SELECT is_available FROM resources WHERE id = 'R1'")
    assert res_res[0]['is_available'] is False
    
    # VERIFY: Network calls
    assert session_route.called
    assert agent_route.called
    
    # 5. Second tick: Reconciliation Logic
    # ----------------------------------
    # SIMULATE: Task finishes (e.g. by agent updating DB)
    execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = 'T1'")
    
    # ACT: Second Cycle
    run_scheduler_tick()
    
    # VERIFY: Database state after reconciliation
    res_reconciled = execute_query("SELECT is_available FROM resources WHERE id = 'R1'")
    assert res_reconciled[0]['is_available'] is True
    
    print(">>> Integration test test_full_pool_dispatch_and_reconcile PASSED on REAL DB.")
