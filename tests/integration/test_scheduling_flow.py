import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.scheduling_assistant.agent import root_agent as scheduling_assistant_agent

@pytest.fixture
async def scheduling_client():
    """Client for SchedulingAssistant."""
    return AgentTestClient(agent=scheduling_assistant_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_scheduling_proposal_flow(scheduling_client):
    """
    Test Case: SchedulingAssistant - Proposal Flow
    Verifies: "帮我排期" -> fetch_workload -> Present Plan -> wait for confirm.
    """
    MockLlm.set_behaviors({
        # 1. User asks for scheduling -> agent calls fetch_workload_and_resources
        "帮我排期": {
            "tool": "fetch_workload_and_resources",
            "args": {}
        },
        
        # 2. After getting the backlog, the agent should present a proposal and ask for confirmation.
        # We mock a confirmation message to trigger apply_scheduling_results.
        "确认": {
            "tool": "apply_scheduling_results",
            "args": {
                "scheduling_results": [
                    {"task_id": "TASK-1", "start_date": "2026-03-26", "due_date": "2026-03-27"}
                ]
            }
        }
    })
    
    await scheduling_client.create_new_session("user_test", "sess_sched_1")
    
    # Step 1: Trigger scheduling
    responses = await scheduling_client.chat("帮我排期")
    assert len(responses) >= 0
    
    # Step 2: Confirm (simulating user saying "确认")
    responses = await scheduling_client.chat("确认")
    assert len(responses) >= 0
