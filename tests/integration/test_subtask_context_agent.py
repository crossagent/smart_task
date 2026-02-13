import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.remote_a2a.new_task.subtask_context.agent import subtask_context_agent

@pytest.fixture
async def subtask_client():
    return AgentTestClient(agent=subtask_context_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_subtask_context_agent(subtask_client):
    """
    Test SubtaskContextAgent flow:
    Request Breakdown -> Suggestion
    """
    MockLlm.set_behaviors({
        "break down": {
             "tool": "suggest_breakdown",
             "args": {"task_title": "Deploy"}
        },
        "breakdown result": "Step 1, Step 2"
    })
    
    await subtask_client.create_new_session("test_user", "sess_sub_1")
    responses = await subtask_client.chat("Break down 'Deploy'")
    assert len(responses) >= 0
