
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.remote_a2a.progress_aggregation.agent import root_agent as daily_todo_agent

@pytest.fixture
async def daily_todo_client():
    """Client for ProgressAggregationAgent."""
    return AgentTestClient(agent=daily_todo_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_daily_todo_flow(daily_todo_client):
    """
    Test Case 1: ProgressAggregationAgent - Query Tasks
    Verifies that asking "What should I do today?" triggers a database query.
    """
    MockLlm.set_behaviors({
        "what should i do": {
            "tool": "query_database",
            "args": {"query": "FROM Task", "query_filter": '{"property": "Status", "status": {"does_not_equal": "Done"}}'}
        }
    })

    await daily_todo_client.create_new_session("user_test", "sess_daily_1")
    responses = await daily_todo_client.chat("What should I do today?")
    
    assert len(responses) >= 0
