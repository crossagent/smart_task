import os
import pytest
from google.adk.models import LLMRegistry
from tests.test_core.mock_llm import MockLlm


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

from unittest.mock import MagicMock
import notion_client

@pytest.fixture(autouse=True)
def mock_notion_writes(monkeypatch):
    """
    Safety fixture: Automatically mock Notion write operations (pages.create) 
    to prevent accidental writes to the production database during tests.
    """
    # We patch the Client class in notion_client module so it affects all imports
    original_init = notion_client.Client.__init__

    def safe_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Mock the pages.create method which is used for writing tasks
        self.pages = MagicMock()
        self.pages.create.return_value = {"id": "mock_safe_test_id"}
        
    monkeypatch.setattr(notion_client.Client, "__init__", safe_init)
