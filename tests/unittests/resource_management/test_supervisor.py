import pytest
import os
import yaml
import time
from unittest.mock import MagicMock, patch
from src.supervisor import AgentSupervisor

@pytest.fixture
def config_data():
    return {
        "db_url": "postgresql://test_db",
        "agents_pool": [
            {
                "id": "test-agent",
                "resource_id": "RES-TEST",
                "dir": "tests/mock_agent",
                "port": 9999,
                "default_workspace": "/tmp/work"
            }
        ]
    }

@pytest.fixture
def supervisor(tmp_path, config_data):
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Initialize with the temporary config
    return AgentSupervisor(config_path=str(config_file))

def test_load_config(supervisor):
    supervisor.load_config()
    assert supervisor.db_url == "postgresql://test_db"
    assert "RES-TEST" in supervisor.pool
    handle = supervisor.pool["RES-TEST"]
    assert handle.port == 9999
    assert handle.dir == "tests/mock_agent"

@patch("src.supervisor.subprocess.Popen")
def test_bootstrap_starts_processes(mock_popen, supervisor):
    supervisor.bootstrap()
    
    # Verify Popen was called
    assert mock_popen.called
    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert "api_server" in cmd
    assert "9999" in cmd
    
    # Verify env vars
    env = kwargs["env"]
    assert env["SESSION_SERVICE_URI"] == "postgresql://test_db"
    assert env["SMART_WORKSPACE_PATH"] == "/tmp/work"

@patch("src.supervisor.subprocess.Popen")
def test_watchdog_restarts_dead_agent(mock_popen, supervisor):
    # 1. Simulate initial startup
    mock_proc_1 = MagicMock()
    mock_proc_1.poll.return_value = None # Process is running
    mock_popen.return_value = mock_proc_1
    
    supervisor.bootstrap()
    handle = supervisor.pool["RES-TEST"]
    assert handle.is_alive()
    
    # 2. Simulate process death
    mock_proc_1.poll.return_value = 1 # Process died
    assert not handle.is_alive()
    
    # 3. Prepare second mock process for restart
    mock_proc_2 = MagicMock()
    mock_proc_2.poll.return_value = None
    mock_popen.return_value = mock_proc_2

    # Simulate Watchdog reconciliation
    supervisor._reconcile_pool()
        
    # Verify Popen called twice
    assert mock_popen.call_count >= 2
    # Verify handle bound to new process
    assert handle.process == mock_proc_2
    assert handle.is_alive()
    
def test_get_agent_url(supervisor):
    supervisor.load_config()
    url = supervisor.get_agent_url("RES-TEST")
    assert url == "http://localhost:9999"
    
    # Invalid ID returns None
    assert supervisor.get_agent_url("INVALID") is None
