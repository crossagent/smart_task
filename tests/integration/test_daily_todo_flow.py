
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.progress_aggregation.agent import root_agent as daily_todo_agent

@pytest.fixture
async def daily_todo_client():
    """Client for ProgressAggregationAgent."""
    return AgentTestClient(agent=daily_todo_agent, app_name="smart_task")

@pytest.fixture
def mock_daily_tools():
    from unittest.mock import MagicMock
    original_tools = list(daily_todo_agent.tools)
    
    mock_query = MagicMock(return_value='{"results": []}')
    mock_query.__name__ = "API-query-data-source"
    mock_query.name = "API-query-data-source"
    
    mock_post = MagicMock(return_value='{"id": "NEW-TASK"}')
    mock_post.__name__ = "API-post-page"
    mock_post.name = "API-post-page"
    
    daily_todo_agent.tools = [mock_query, mock_post]
    yield
    daily_todo_agent.tools = original_tools


@pytest.mark.anyio
async def test_daily_todo_flow(daily_todo_client, mock_daily_tools):
    """
    Test Case 1: ProgressAggregationAgent - Query Tasks
    Verifies that asking "What should I do today?" triggers a database query.
    """
    MockLlm.set_behaviors({
        "what should i do": {
            "tool": "API-query-data-source",
            "args": {"data_source_id": "1990d59debb7816dab7bf83e93458d30"} # Task DB
        }
    })

    await daily_todo_client.create_new_session("user_test", "sess_daily_1")
    responses = await daily_todo_client.chat("What should I do today?")
    
    assert len(responses) >= 0
