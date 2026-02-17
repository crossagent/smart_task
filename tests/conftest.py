import os
import pytest
from dotenv import load_dotenv
from google.adk.models import LLMRegistry
from tests.test_core.mock_llm import MockLlm

# Load environment variables from .env file
load_dotenv()


def pytest_configure(config):
    """
    Set up environment for testing BEFORE any imports happen.
    This ensures constants.py picks up the mock model.
    """
    # Set mock model for all tests by default
    os.environ["GOOGLE_GENAI_MODEL"] = "mock/pytest"
    print(">>> [conftest] Set GOOGLE_GENAI_MODEL=mock/pytest")


@pytest.fixture(scope="session", autouse=True)
def register_mock_llm():
    """
    Automatically register the MockLlm provider at the start of the test session.
    This ensures 'mock/...' models are available to all tests.
    """
    print(">>> [conftest] Registering MockLlm...")
    LLMRegistry.register(MockLlm)
    

@pytest.fixture(autouse=True)
def reset_mock_behaviors():
    """
    Reset mock behaviors before each test to ensure isolation.
    """
    MockLlm.clear_behaviors()


@pytest.fixture(autouse=True)
def configure_agents_mock_model():
    """
    Force all agents to use the mock model for testing.
    This overrides any hardcoded 'gemini-2.5-flash' in the agent definitions.
    """
    from smart_task_app.task_decomposition.agent import root_agent as task_decomposition_agent
    from smart_task_app.progress_aggregation.agent import root_agent as progress_aggregation_agent
    
    agents = [
        task_decomposition_agent,
        progress_aggregation_agent,
    ]
    
    for agent in agents:
        agent.model = "mock/pytest"

@pytest.fixture
def anyio_backend():
    return 'asyncio'

