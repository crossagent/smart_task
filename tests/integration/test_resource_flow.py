import pytest
import respx
import httpx
from unittest.mock import MagicMock, patch
from src.task_execution.scheduler import run_scheduler_tick
from src.resource_management.workspace_lock import workspace_lock_manager, LOCK_FILE_NAME
from src.resource_management.supervisor import agent_supervisor

@pytest.fixture
def mock_db():
    def mock_exists_logic(self):
        if str(self).endswith(LOCK_FILE_NAME):
            return False
        return True

    with patch("src.task_execution.scheduler.execute_query") as m_query, \
         patch("src.task_execution.scheduler.execute_mutation") as m_mutate, \
         patch("src.resource_management.workspace_lock.Path.exists", side_effect=mock_exists_logic, autospec=True), \
         patch("src.resource_management.workspace_lock.Path.write_text"), \
         patch("src.resource_management.workspace_lock.Path.unlink"):
        yield m_query, m_mutate

@respx.mock
def test_full_pool_dispatch_and_reconcile(mock_db):
    m_query, m_mutate = mock_db
    
    # 1. Setup states
    workspace_lock_manager._active_locks = {}
    agent_supervisor.pool = {
        "R1": MagicMock(url="http://agent-r1:9001")
    }

    # First tick: Promotion + Dispatch
    # Mock data return for Tick 1
    m_query.side_effect = [
        [], # Promote pending (none)
        [], # Reconcile (none)
        [   # Ready tasks for dispatch
            {
                'task_id': 'T1', 
                'res_id': 'R1', 
                'workspace_path': '/work/w1',
                'module_iteration_goal': 'Build a feature'
            }
        ]
    ]

    # Mock the Agent API endpoint
    agent_route = respx.post("http://agent-r1:9001/invocations").respond(200, json={"status": "accepted"})
    
    # Mock threading.Thread to run target synchronously for testing
    with patch("src.task_execution.scheduler.threading.Thread") as mock_thread:
        # Create a mock thread instance that calls target immediately
        def sync_run(target, args=(), kwargs={}, daemon=True):
            target(*args, **kwargs)
            return MagicMock() # Return a mock handle
        
        mock_thread.side_effect = sync_run
        
        # Run Tick 1 (Dispatch)
        run_scheduler_tick()
    
    # Verify Dispatch
    assert workspace_lock_manager.is_locked('/work/w1') is True
    m_mutate.assert_any_call("UPDATE resources SET is_available = False WHERE id = %s", ("R1",))
    m_mutate.assert_any_call("UPDATE tasks SET status = 'in_progress' WHERE id = %s", ("T1",))
    
    # Verify HTTP call was made
    assert agent_route.called
    
    # Second tick: Reconciliation
    # Now simulate that T1 is finished (status='code_done' in DB)
    m_query.side_effect = [
        [], # Promote
        [   # Reconciliation: find one task that is done but resource is busy
            {
                'id': 'T1',
                'resource_id': 'R1',
                'workspace_path': '/work/w1'
            }
        ],
        []  # Dispatch (none)
    ]
    
    # Run Tick 2 (Reconcile)
    run_scheduler_tick()
    
    # Verify Cleanup
    assert workspace_lock_manager.is_locked('/work/w1') is False
    m_mutate.assert_any_call("UPDATE resources SET is_available = True WHERE id = %s", ("R1",))

def test_conflict_deferral(mock_db):
    m_query, m_mutate = mock_db
    workspace_lock_manager._active_locks = {}
    
    # Pre-lock workspace
    norm_path = workspace_lock_manager._normalize_path('/work/w1')
    workspace_lock_manager._active_locks[norm_path] = 'OTHER_TASK'
    
    # Mock data
    m_query.side_effect = [
        [], # Promote
        [], # Reconcile
        [   # Ready tasks
            {
                'task_id': 'T1', 
                'res_id': 'R1', 
                'workspace_path': '/work/w1',
                'module_iteration_goal': 'Goal'
            }
        ]
    ]
    
    run_scheduler_tick()
    
    # Should NOT have updated T1 status to in_progress
    for call in m_mutate.call_args_list:
        if "TSK-001" in str(call): # using the task ID from call logic
            assert False, "Task T1 should not have been dispatched"
    # Or more direct check:
    assert m_mutate.call_count == 0
