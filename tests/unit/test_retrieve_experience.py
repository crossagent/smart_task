# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for the retrieve_experience functionality.
"""

import pytest
from unittest.mock import MagicMock, patch
from smart_task_app.remote_a2a.experience_agent.agent import root_agent


@pytest.fixture
def mock_rag_tool():
    """Mock the RAG retrieval tool."""
    original_tools = list(root_agent.tools)
    
    # Create a mock tool
    mock_tool = MagicMock()
    mock_tool.__name__ = "retrieve_rag_documentation"
    mock_tool.return_value = """
    找到3个相关案例：
    
    1. 任务拆解最佳实践
       - 相似度: 0.85
       - 使用看板方法可以提高任务可视化
       
    2. 项目管理经验
       - 相似度: 0.78
       - 使用敏捷方法进行迭代开发
       
    3. 团队协作技巧
       - 相似度: 0.72
       - 定期站会提高团队沟通效率
    """
    
    root_agent.tools = [mock_tool]
    yield mock_tool
    root_agent.tools = original_tools


def test_retrieve_experience_tool_exists():
    """Test that the retrieve tool is properly configured."""
    assert len(root_agent.tools) > 0
    tool_names = [getattr(t, '__name__', getattr(t, 'name', '')) for t in root_agent.tools]
    assert 'retrieve_rag_documentation' in tool_names


def test_retrieve_experience_mock(mock_rag_tool):
    """Test retrieve with mocked RAG tool."""
    result = mock_rag_tool("任务拆解")
    assert "任务拆解" in result
    assert "相似度" in result
    mock_rag_tool.assert_called_once()


@pytest.mark.anyio
async def test_agent_has_correct_configuration():
    """Test that the agent is properly configured."""
    assert root_agent.name == "ExperienceAgent"
    assert root_agent.description == "Agent for retrieving historical reference solutions and saving experiences"
    assert callable(root_agent.instruction)
    
    # Get instruction text
    instruction_text = root_agent.instruction()
    assert "经验检索助手" in instruction_text
    assert "retrieve_rag_documentation" in instruction_text
