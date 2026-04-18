import pytest

from experts.coder_expert.agent import root_agent, execute_shell

def test_coder_agent_loads():
    """Verify the coder agent definition loads correctly."""
    assert root_agent.name == "coder_expert"
    assert len(root_agent.tools) == 2

def test_tool_execute_shell():
    """Test bash execution wrapper locally."""
    res = execute_shell("echo hello")
    assert "hello" in res
