import os
import pytest
from google.adk.models import LLMRegistry
from tests.test_core.mock_llm import MockLlm


def pytest_configure(config):
    """
    Set up environment for testing BEFORE any imports happen.
    This ensures constants.py picks up the mock model.
    """
    # Set mock model for all tests by default
    os.environ["GOOGLE_GENAI_MODEL"] = "mock/pytest"
    print(">>> [conftest] Set GOOGLE_GENAI_MODEL=mock/pytest")


@pytest.fixture(scope="session", autouse=True)
def register_mock_llm():
    """
    Automatically register the MockLlm provider at the start of the test session.
    This ensures 'mock/...' models are available to all tests.
    """
    print(">>> [conftest] Registering MockLlm...")
    LLMRegistry.register(MockLlm)
    

@pytest.fixture(autouse=True)
def reset_mock_behaviors():
    """
    Reset mock behaviors before each test to ensure isolation.
    """
    MockLlm.clear_behaviors()

from unittest.mock import MagicMock
import notion_client

@pytest.fixture(autouse=True)
def mock_notion_writes(monkeypatch):
    """
    Safety fixture: Automatically mock Notion write operations (pages.create) 
    to prevent accidental writes to the production database during tests.
    """
    # We patch the Client class in notion_client module so it affects all imports
    original_init = notion_client.Client.__init__

    def safe_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Mock the pages.create method which is used for writing tasks
        self.pages = MagicMock()
        self.pages.create.return_value = {"id": "mock_safe_test_id"}
        
    monkeypatch.setattr(notion_client.Client, "__init__", safe_init)


@pytest.fixture(autouse=True)
def configure_agents_mock_model():
    """
    Force all agents to use the mock model for testing.
    This overrides any hardcoded 'gemini-2.5-flash' in the agent definitions.
    """
    from smart_task_app.remote_a2a.new_task.agent import root_agent as new_task_agent
    from smart_task_app.remote_a2a.new_task.project_context.agent import project_context_agent
    from smart_task_app.remote_a2a.new_task.task_context.agent import task_context_agent
    from smart_task_app.remote_a2a.new_task.subtask_context.agent import subtask_context_agent
    
    agents = [
        new_task_agent,
        project_context_agent,
        task_context_agent,
        subtask_context_agent
    ]
    
    for agent in agents:
        agent.model = "mock/pytest"

import subprocess
import time
import urllib.request
import sys

@pytest.fixture(scope="session", autouse=True)
def start_a2a_server():
    """
    Automatically start the A2A remote server for the duration of the test session.
    This removes the need to manually run start_root_agent.ps1.
    """
    print(f">>> [conftest] Starting A2A Server on port 28001...")
    
    # Command to start the server: python -m google.adk.cli api_server ...
    cmd = [
        sys.executable, "-m", "google.adk.cli", 
        "api_server", "smart_task_app/remote_a2a", 
        "--a2a", "--port", "28001"
    ]
    
    # We need to set PYTHONPATH so it can find smart_task_app modules
    env = os.environ.copy()
    if "PYTHONPATH" not in env:
        env["PYTHONPATH"] = os.getcwd()
    else:
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env["PYTHONPATH"]

    # Start process
    try:
        # Redirect stdout/stderr to a file to prevent pipe buffer deadlock
        log_file = open("server_startup.log", "w")
        proc = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=log_file,
            cwd=os.getcwd(), 
            env=env
        )
    except Exception as e:
        print(f">>> [conftest] FAILED TO START SERVER: {e}")
        raise e
    
    # Wait for server to be ready
    # Check DailyTodo agent card as health check
    server_url = "http://localhost:28001/a2a/daily_todo/.well-known/agent-card.json"
    timeout = 30 # seconds
    start_time = time.time()
    
    server_ready = False
    print(f">>> [conftest] Waiting for server at {server_url}...")
    
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(server_url) as response:
                if response.status == 200:
                    print(">>> [conftest] A2A Server is ready!")
                    server_ready = True
                    break
        except Exception:
            time.sleep(1)
            
    if not server_ready:
        print(">>> [conftest] Server timed out. Checking output...")
        proc.terminate()
        try:
            # Output is in log file, print last lines
            log_file.close() # Flush and close for reading
            with open("server_startup.log", "r") as f:
                content = f.read()
                print(f"Server Log:\n{content[-1000:]}")
        except Exception:
            pass
            
        raise RuntimeError(f"A2A Server failed to start within {timeout} seconds")

    yield

    print(">>> [conftest] Stopping A2A Server...")
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    log_file.close()
