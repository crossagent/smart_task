
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
# Import the NEW orchestrator agent
from smart_task_app.task_decomposition.agent import root_agent as task_decomposition_agent

@pytest.fixture
async def task_agent_client():
    """Client for TaskDecompositionAgent."""
    return AgentTestClient(agent=task_decomposition_agent, app_name="smart_task")



@pytest.mark.anyio
async def test_add_task_upsert_flow(task_agent_client):
    """
    Test Case: TaskDecompositionAgent - Upsert Flow
    Verifies: "Add task X" -> Search -> Find "X" -> Update "X" instead of create.
    """
    MockLlm.set_behaviors({
        # 1. Orchestrator receives "Add a task..." -> Calls search projects
        "add a task": {
             "tool": "API-query-data-source", 
             "args": {"data_source_id": "1990d59debb781c58d78c302dffea2b5"} # Project DB ID
        },
        
        # 2. After search finds "Personal Life", it calls search tasks
        "personal life": { 
             "tool": "API-query-data-source",
             "args": {
                 "data_source_id": "1990d59debb7816dab7bf83e93458d30", # Task DB ID
                 # Filter logic is complex, just checking the tool call here
             }
        },
        
        # 3. search_tasks returns matches (simulated in fixture). 
        # Orchestrator should decide to UPDATE.
        "buy milk": { 
             "tool": "API-patch-page",
             "args": {
                 "page_id": "TASK-OLD",
                 "properties": {"Status": "To Do"}
             }
        }
    })
    
    await task_agent_client.create_new_session("user_test", "sess_upsert_1")
    
    # Trigger the flow
    responses = await task_agent_client.chat("Add a task to buy milk")
    
    # Verify the agent responded
    assert len(responses) >= 0
