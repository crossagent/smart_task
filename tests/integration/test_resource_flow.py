import pytest
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

def test_full_dispatch_flow(mock_db):
    m_query, m_mutate = mock_db
    
    # Reset singleton states
    workspace_lock_manager._active_locks = {}
    agent_supervisor.active_agents = {}

    # Mock data for ready tasks
    # Task 1 needs Resource R1 (Workspace W1)
    m_query.side_effect = [
        [], # Promote pending (none)
        [   # Ready tasks
            {
                'task_id': 'T1', 
                'res_id': 'R1', 
                'agent_dir': '/agents/a1', 
                'workspace_path': '/work/w1'
            }
        ]
    ]

    # Mock supervisor.dispatch to return a handle
    with patch("src.resource_management.supervisor.AgentSupervisor.dispatch") as m_dispatch:
        mock_handle = MagicMock()
        m_dispatch.return_value = mock_handle
        
        # Run tick
        run_scheduler_tick()
        
        # Verify Workspace is locked
        assert workspace_lock_manager.is_locked('/work/w1') is True
        
        # Verify Mutations: resource busy, task in_progress
        m_mutate.assert_any_call("UPDATE resources SET is_available = False WHERE id = %s", ("R1",))
        m_mutate.assert_any_call("UPDATE tasks SET status = 'in_progress' WHERE id = %s", ("T1",))
        
        # Verify Dispatch called
        m_dispatch.assert_called_once_with('T1', 'R1', '/agents/a1', '/work/w1')
        
        # Verify Cleanup Callback Registration
        mock_handle.on_complete.assert_called_once()
        
        # Simulate completion via callback
        # Extract the lambda and call it
        callback = mock_handle.on_complete.call_args[0][0]
        callback(mock_handle)
        
        # Verify Cleanup: Workspace unlocked, Resource released
        assert workspace_lock_manager.is_locked('/work/w1') is False
        m_mutate.assert_any_call("UPDATE resources SET is_available = True WHERE id = %s", ("R1",))

def test_conflict_deferral(mock_db):
    m_query, m_mutate = mock_db
    workspace_lock_manager._active_locks = {}
    
    # Workspace W1 is ALREADY locked by another process/task
    # Normalize it so it matches what the manager uses
    norm_path = workspace_lock_manager._normalize_path('/work/w1')
    workspace_lock_manager._active_locks[norm_path] = 'OTHER_TASK'
    
    m_query.side_effect = [
        [], # Promote pending
        [   # Ready tasks
            {
                'task_id': 'T1', 
                'res_id': 'R1', 
                'agent_dir': '/agents/a1', 
                'workspace_path': '/work/w1'
            }
        ]
    ]
    
    with patch("src.resource_management.supervisor.AgentSupervisor.dispatch") as m_dispatch:
        run_scheduler_tick()
        
        # Should NOT dispatch because workspace is locked
        m_dispatch.assert_not_called()
        # Should NOT update DB
        # Note: it might have been called with other things, but not for T1
        for call in m_mutate.call_args_list:
            assert 'T1' not in call[0][1]
