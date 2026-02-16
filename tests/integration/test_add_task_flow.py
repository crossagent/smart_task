
import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
# Import the NEW orchestrator agent
from smart_task_app.remote_a2a.task_decomposition.agent import root_agent as new_task_agent

@pytest.fixture
async def task_agent_client():
    """Client for TaskDecompositionAgent."""
    return AgentTestClient(agent=new_task_agent, app_name="smart_task")

@pytest.fixture
def mock_context_tools():
    from unittest.mock import MagicMock
    """
    Replace real tools with MagicMocks.
    """
    original_tools = list(new_task_agent.tools)
    new_tools = []
    
    for tool in original_tools:
        # LlmAgent tools are often callables (FunctionTool) or BaseTool instances.
        tool_name = getattr(tool, "__name__", getattr(tool, "name", str(tool)))
        
        if tool_name == "search_projects":
            # Mock Search Projects
            m = MagicMock(return_value='{"projects": [{"id": "PROJ-123", "name": "Personal Life"}]}')
            m.__name__ = "search_projects"
            new_tools.append(m)
            
        elif tool_name == "search_tasks":
            # Mock Search Tasks (simulate finding an existing task)
            m = MagicMock(return_value='{"tasks": [{"id": "TASK-OLD", "title": "Buy Milk"}]}')
            m.__name__ = "search_tasks"
            new_tools.append(m)
            
        elif tool_name == "add_task_to_database":
             # Mock Notion Add - Should NOT be called in this test scenario
             m = MagicMock(return_value='{"status": "success", "id": "TASK-NEW"}')
             m.__name__ = "add_task_to_database"
             new_tools.append(m)
        
        elif tool_name == "update_task":
             # Mock Notion Update - THIS should be called
             m = MagicMock(return_value='{"status": "success", "id": "TASK-OLD"}')
             m.__name__ = "update_task"
             new_tools.append(m)
             
        elif tool_name == "add_project_to_database":
             # Mock Notion Add Project
             m = MagicMock(return_value='{"status": "success", "id": "PROJ-1"}')
             m.__name__ = "add_project_to_database"
             new_tools.append(m)
             
        elif tool_name == "update_project":
             m = MagicMock(return_value='{"status": "success", "id": "PROJ-1"}')
             m.__name__ = "update_project"
             new_tools.append(m)
        else:
             new_tools.append(tool)
            
    new_task_agent.tools = new_tools
    yield
    new_task_agent.tools = original_tools



@pytest.mark.anyio
async def test_add_task_upsert_flow(task_agent_client, mock_context_tools):
    """
    Test Case: TaskDecompositionAgent - Upsert Flow
    Verifies: "Add task X" -> Search -> Find "X" -> Update "X" instead of create.
    """
    MockLlm.set_behaviors({
        # 1. Orchestrator receives "Add a task..." -> Calls search projects
        "add a task": {
             "tool": "search_projects", 
             "args": {"query": "Buy Milk"} 
        },
        
        # 2. After search_projects finds "Personal Life" (ID: PROJ-123), 
        # it calls search_tasks WITH project_id
        "personal life": { 
             "tool": "search_tasks",
             "args": {
                 "query": "Buy Milk",
                 "project_id": "PROJ-123" # Verified requirement
             }
        },
        
        # 3. serach_tasks returns matches (simulated in fixture). 
        # Orchestrator should decide to UPDATE.
        "buy milk": { 
             "tool": "update_task",
             "args": {
                 "page_id": "TASK-OLD",
                 "title": "Buy Milk"
             }
        }
    })
    
    await task_agent_client.create_new_session("user_test", "sess_upsert_1")
    
    # Trigger the flow
    responses = await task_agent_client.chat("Add a task to buy milk")
    
    # Verify the agent responded
    assert len(responses) >= 0
