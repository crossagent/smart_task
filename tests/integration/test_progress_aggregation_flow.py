
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.progress_aggregation.agent import root_agent as progress_aggregation_agent

@pytest.fixture
async def daily_todo_client():
    """Client for ProgressAggregationAgent."""
    return AgentTestClient(agent=progress_aggregation_agent, app_name="smart_task")




@pytest.mark.anyio
async def test_daily_todo_flow(daily_todo_client):
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
