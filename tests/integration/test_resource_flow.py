import pytest
import respx
import httpx
from unittest.mock import MagicMock, patch
# Import the actual core cycle - tests might have been using an older name
from src.task_execution.scheduler import run_system_bus_cycle as run_scheduler_tick
from src.resource_management.supervisor import agent_supervisor

@pytest.fixture
def mock_db():
    with patch("src.task_execution.scheduler.execute_query") as m_query, \
         patch("src.task_execution.scheduler.execute_mutation") as m_mutate:
        yield m_query, m_mutate

@respx.mock
def test_full_pool_dispatch_and_reconcile(mock_db):
    m_query, m_mutate = mock_db
    
    # 1. Setup states
    agent_supervisor.pool = {
        "R1": MagicMock(url="http://agent-r1:9001")
    }

    # First tick: Promotion + Dispatch
    # Mock data return for Tick 1
    m_query.side_effect = [
        [], # Promote pending (none)
        [   # System state
            {'key': 'run_mode', 'value': 'auto'},
            {'key': 'step_count', 'value': '0'}
        ],
        [], # Promote pending (dependencies)
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
    agent_route = respx.post("http://agent-r1:9001/run").respond(200, json={"status": "accepted"})
    
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
    m_mutate.assert_any_call("UPDATE resources SET is_available = False WHERE id = %s", ("R1",), connection=pytest.any)
    m_mutate.assert_any_call("UPDATE tasks SET status = 'in_progress' WHERE id = %s", ("T1",), connection=pytest.any)
    
    # Verify HTTP call was made
    assert agent_route.called
    
    # Second tick: Reconciliation
    # Now simulate that T1 is finished (status='code_done' in DB)
    m_query.side_effect = [
        [], # Interrupts
        [], # Human interventions
        [   # System state
            {'key': 'run_mode', 'value': 'auto'},
            {'key': 'step_count', 'value': '0'}
        ],
        [], # Promote
        [], # Dispatch
        [   # Reconciliation: find one task that is done but resource is busy
            {
                'id': 'T1',
                'resource_id': 'R1',
                'workspace_path': '/work/w1'
            }
        ]
    ]
    
    # Run Tick 2 (Reconcile)
    run_scheduler_tick()
    
    # Verify Cleanup
    m_mutate.assert_any_call("UPDATE resources SET is_available = True WHERE id = %s", ("R1",), connection=pytest.any)
