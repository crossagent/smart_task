
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.agent import root_agent

@pytest.fixture
async def smart_task_client():
    """Client for SmartTaskAgent (Root)."""
    return AgentTestClient(agent=root_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_smart_task_dispatch(smart_task_client):
    """
    Test Case 3: SmartTaskAgent - Dispatch
    Verifies routing to specific sub-agents.
    """
    MockLlm.set_behaviors({
        "add a task": {
            "tool": "run_addtaskworkflow",
            "args": {}
        }
    })
    
    await smart_task_client.create_new_session("user_test", "sess_dispatch_1")
    responses = await smart_task_client.chat("I want to add a task")
    
    pass
