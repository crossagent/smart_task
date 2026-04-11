import pytest
import subprocess
from unittest.mock import MagicMock, patch
from src.resource_management.supervisor import AgentSupervisor, AgentHandle

@pytest.fixture
def supervisor():
    return AgentSupervisor()

def test_agent_handle_trigger_complete():
    callback = MagicMock()
    handle = AgentHandle("T1", "R1")
    handle.on_complete(callback)
    
    handle._trigger_complete()
    callback.assert_called_once_with(handle)

@patch("src.resource_management.supervisor.execute_mutation")
@patch("src.resource_management.supervisor.subprocess.Popen")
def test_supervisor_dispatch_and_success(mock_popen, mock_mutation, supervisor):
    # Mock process
    mock_proc = MagicMock()
    mock_proc.stdout = ["line 1", "line 2"]
    mock_proc.returncode = 0
    mock_proc.poll.return_value = 0 # Finished
    mock_popen.return_value = mock_proc
    
    task_id = "TSK-001"
    res_id = "RES-001"
    agent_dir = "/path/to/agent"
    workspace = "/path/to/work"
    
    handle = supervisor.dispatch(task_id, res_id, agent_dir, workspace)
    
    # We need to wait for the thread to finish in testing
    # Since it's a daemon thread, we wait for a bit or join (if we had access)
    # A better way is to wait for the handle to be removed from active_agents
    import time
    timeout = 5
    start_time = time.time()
    while task_id in supervisor.active_agents and time.time() - start_time < timeout:
        time.sleep(0.1)
        
    assert task_id not in supervisor.active_agents
    mock_popen.assert_called_once()
    # Check if code_done mutation was called
    mock_mutation.assert_any_call("UPDATE tasks SET status = 'code_done' WHERE id = %s AND status = 'in_progress'", (task_id,))

@patch("src.resource_management.supervisor.execute_mutation")
def test_supervisor_mock_execution(mock_mutation, supervisor):
    task_id = "TSK-MOCK"
    
    # agent_dir=None triggers mock execution
    # Monkeypatch time.sleep before dispatching to ensure the thread sees it
    with patch("time.sleep"):
        handle = supervisor.dispatch(task_id, "RES-1", None, "/some/path")
        
        # Wait for completion
        import time
        start_time = time.time()
        while task_id in supervisor.active_agents and time.time() - start_time < 5:
            time.sleep(0.01)
            
    # Verify mutation happened
    mock_mutation.assert_any_call("UPDATE tasks SET status = 'code_done' WHERE id = %s", (task_id,))
