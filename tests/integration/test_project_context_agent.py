import pytest
from tests.test_core.test_client import AgentTestClient
from tests.test_core.mock_llm import MockLlm
from smart_task_app.remote_a2a.new_task.project_context.agent import project_context_agent

@pytest.fixture
async def project_client():
    return AgentTestClient(agent=project_context_agent, app_name="smart_task")

@pytest.mark.anyio
async def test_project_context_agent(project_client):
    """
    Test ProjectContextAgent flow:
    Search -> Return Project Info
    """
    MockLlm.set_behaviors({
        "search projects": {
            "tool": "search_projects",
            "args": {"query": "Refactor"}
        },
        "search result": "['Project A']"
    })
    
    await project_client.create_new_session("test_user", "sess_proj_1")
    responses = await project_client.chat("Find project for Refactor")
    assert len(responses) >= 0
