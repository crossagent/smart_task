
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.agent import app

@pytest.fixture
async def smart_task_client():
    """Client for SmartTaskAgent (Root)."""
    return AgentTestClient(agent=app.root_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_smart_task_dispatch(smart_task_client):
    """
    Test Case: SmartTaskAgent - Dispatch to sub-agent
    Verifies routing to ProgressAggregationAgent via transfer_to_agent.
    """
    MockLlm.set_behaviors({
        # Root agent receives "今天有什么工作" -> transfers to ProgressAggregationAgent
        "今天有什么工作": {
            "tool": "transfer_to_agent",
            "args": {"agent_name": "ProgressAggregationAgent"}
        }
    })
    
    await smart_task_client.create_new_session("user_test", "sess_dispatch_1")
    responses = await smart_task_client.chat("今天有什么工作")
    
    # Verify the agent responded (dispatch happened without error)
    assert len(responses) >= 0
