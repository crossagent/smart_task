"""
Integration tests for Bug Sleuth root agent flow.
Uses app_factory for unified initialization.

Model selection is handled via GOOGLE_GENAI_MODEL environment variable
(set in conftest.py to "mock/pytest" for all tests).

Note: Tests use real config.yaml for REPO_REGISTRY.
Only external tool checks (ripgrep) are mocked.
"""
import pytest
import logging
from unittest.mock import patch

from bug_sleuth.app_factory import create_app, AppConfig
from bug_sleuth.testing import AgentTestClient, MockLlm
from bug_sleuth.shared_libraries.state_keys import StateKeys

logging.basicConfig(level=logging.INFO)


@pytest.fixture
def mock_external_deps():
    """
    Only mock external tool availability checks, not config.
    REPO_REGISTRY comes from real config.yaml.
    """
    # Explicitly import to ensure module is attached to parent package for patching
    import bug_sleuth.bug_scene_app.bug_analyze_agent.agent

    with patch("bug_sleuth.bug_scene_app.bug_analyze_agent.agent.check_search_tools", 
               return_value=None):
        yield


@pytest.mark.anyio
async def test_root_agent_refine_bug_state_tool(mock_external_deps):
    """
    Test that root agent can call refine_bug_state tool.
    Verifies: Agent receives input -> Calls tool -> Returns response
    """
    MockLlm.set_behaviors({
        "logo is overlapping": {
            "tool": "refine_bug_state",
            "args": {
                "bug_description": "The logo is overlapping text on the login screen",
                "device_info": "Android",
                "product_branch": "Branch A"
            }
        }
    })
    
    app = create_app(AppConfig(agent_name="bug_scene_agent"))
    
    client = AgentTestClient(agent=app.agent, app_name="bug_sleuth_app")
    await client.create_new_session("user_test", "sess_001")
    
    responses = await client.chat("The logo is overlapping text on the login screen, Android, Branch A.")
    
    assert len(responses) > 0
    assert "[MockLlm]" in responses[-1]


@pytest.mark.anyio
async def test_root_agent_question_answer_flow(mock_external_deps):
    """
    Test Q&A flow: Agent asks for clarification, user responds.
    """
    MockLlm.set_behaviors({
        "It's broken": {
            "text": "What device are you using?"
        },
        "Pixel 6": {
            "tool": "refine_bug_state",
            "args": {
                "device_name": "Pixel 6"
            }
        }
    })
    
    app = create_app(AppConfig(agent_name="bug_scene_agent"))
    
    client = AgentTestClient(agent=app.agent, app_name="bug_sleuth_app")
    await client.create_new_session("user_test", "sess_002")
    
    resp1 = await client.chat("It's broken")
    assert len(resp1) > 0
    assert "What device" in resp1[-1]
    
    resp2 = await client.chat("I use a Pixel 6")
    assert len(resp2) > 0


@pytest.mark.anyio
async def test_root_agent_dispatch_to_analyze_agent(mock_external_deps):
    """
    Test agent delegation: Root agent dispatches to analyze agent.
    """
    MockLlm.set_behaviors({
        "crashes sometimes": {
            "tool": "refine_bug_state",
            "args": {
                "bug_description": "Game crashes sometimes when opening bag",
                "device_info": "PC"
            }
        },
        "success": {
            "text": "[MockLlm] Delegating to bug_analyze_agent for deep analysis..."
        }
    })
    
    app = create_app(AppConfig(agent_name="bug_scene_agent"))
    
    client = AgentTestClient(agent=app.agent, app_name="bug_sleuth_app")
    await client.create_new_session("user_test", "sess_complex")
    
    responses = await client.chat("Game crashes sometimes when opening bag, PC.")
    
    assert len(responses) > 0


@pytest.mark.anyio
async def test_analyze_agent_git_log_tool(mock_external_deps):
    """
    Test that analyze agent can call get_git_log_tool.
    """
    MockLlm.set_behaviors({
        "check the git logs": {
            "tool": "get_git_log_tool",
            "args": {"limit": 5}
        }
    })
    
    app = create_app(AppConfig(agent_name="bug_analyze_agent"))
    
    client = AgentTestClient(agent=app.agent, app_name="test_app")
    await client.create_new_session("user_1", "sess_1", initial_state={})
    
    responses = await client.chat("Please check the git logs for me.")
    
    assert len(responses) > 0
    assert "[MockLlm]" in responses[-1]


@pytest.mark.anyio
async def test_app_factory_creates_valid_root_agent(mock_external_deps):
    """
    Basic test to verify app_factory returns valid root agent with sub-agents.
    """
    app = create_app(AppConfig(agent_name="bug_scene_agent"))
    
    assert app.agent is not None
    assert app.agent.name == "bug_scene_agent"
    
    # Verify sub-agents are accessible
    analyze_agent = app.get_agent("bug_analyze_agent")
    assert analyze_agent is not None
    assert analyze_agent.name == "bug_analyze_agent"
