"""
Integration tests for Bug Sleuth report agent.
Tests basic flow of report_agent.

Model selection is handled via GOOGLE_GENAI_MODEL environment variable
(set in conftest.py to "mock/pytest" for all tests).
"""
import pytest
from bug_sleuth.app_factory import create_app, AppConfig
from bug_sleuth.testing import AgentTestClient, MockLlm


@pytest.fixture
def report_client():
    """Create a test client for bug_report_agent."""
    app = create_app(AppConfig(agent_name="bug_report_agent"))
    client = AgentTestClient(agent=app.agent, app_name="test_app_report")
    return client


@pytest.mark.anyio
async def test_app_factory_creates_valid_agent():
    """Basic test to verify app_factory returns a valid agent."""
    app = create_app(AppConfig(agent_name="bug_report_agent"))
    
    assert app.agent is not None
    assert app.agent.name == "bug_report_agent"


@pytest.mark.anyio
async def test_chat_basic(report_client):
    """Verifies that the agent can receive a message and return a response."""
    # Since there are no tools, we just check normal chat flow
    # The mock model will return a default response if no specific behavior is set
    
    await report_client.create_new_session("user_1", "sess_report_1", initial_state={})
    responses = await report_client.chat("Hello, I want to report a bug.")
    
    assert len(responses) > 0
    # MockLlm default response usually contains confirmation or just echoes if configured so,
    # but here we just check we got ANY response from the agent.
    assert isinstance(responses[0], str)
