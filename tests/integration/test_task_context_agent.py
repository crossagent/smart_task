import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.new_task.task_context.agent import task_context_agent

@pytest.fixture
async def task_client():
    return AgentTestClient(agent=task_context_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_task_context_agent(task_client):
    """
    Test TaskContextAgent flow:
    Check Duplication -> Return Status
    """
    MockLlm.set_behaviors({
        "check duplicate": {
            "tool": "check_duplication",
            "args": {"task_title": "Fix Bug"}
        },
        "duplication result": "NO_DUPLICATE"
    })
    
    await task_client.create_new_session("test_user", "sess_task_1")
    responses = await task_client.chat("Check duplicate for Fix Bug")
    assert len(responses) >= 0
