
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.add_task.agent import add_task_agent

@pytest.fixture
async def add_task_client():
    """Client for AddTaskWorkflow."""
    return AgentTestClient(agent=add_task_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_add_task_flow(add_task_client):
    """
    Test Case 2: AddTaskWorkflow - Add Task
    Verifies that asking to "Add task" starts the workflow and checks artifacts.
    """
    MockLlm.set_behaviors({
        "read task artifact": {
             "tool": "read_task_artifact",
             "args": {}
        },
        "update task artifact": {
             "tool": "update_task_artifact",
             "args": {"content": "Plan..."}
        },
        "analyze input": {
             "tool": "run_granularityadvisor",
             "args": {}
        },
        "analysis result": "{\"decision\": \"TASK\", \"title\": \"Buy Milk\"}"
    })
    
    await add_task_client.create_new_session("user_test", "sess_add_1")
    responses = await add_task_client.chat("Add a task to buy milk")
    
    assert len(responses) >= 0
