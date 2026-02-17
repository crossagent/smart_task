import os
import sys
from google.adk.agents import LlmAgent

from google.adk.apps import App
from google.adk.sessions import VertexAiSessionService
from google.adk.memory import VertexAiMemoryBankService
from .shared_libraries.constants import MODEL

# Import local implementations of sub-agents
# We use relative imports to avoid hardcoding the package name 'smart_task_app' to be robust
from .task_decomposition.agent import root_agent as LocalTaskDecompositionAgent
from .progress_aggregation.agent import root_agent as LocalProgressAggregationAgent

# Configure Session and Memory services for Vertex AI Express Mode
AGENT_ENGINE_ID = os.environ.get("AGENT_ENGINE_ID")
USE_VERTEX_AI = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() == "TRUE"

if USE_VERTEX_AI and AGENT_ENGINE_ID:
  print(f"[SmartTaskApp] Using Vertex AI Session and Memory (Agent Engine: {AGENT_ENGINE_ID})")
  session_service = VertexAiSessionService(agent_engine_id=AGENT_ENGINE_ID)
  memory_service = VertexAiMemoryBankService(agent_engine_id=AGENT_ENGINE_ID)
else:
  if USE_VERTEX_AI and not AGENT_ENGINE_ID:
    print("[SmartTaskApp] Warning: GOOGLE_GENAI_USE_VERTEXAI=TRUE but AGENT_ENGINE_ID not set")
    print("[SmartTaskApp] Please run: python scripts/setup_agent_engine.py")
  print("[SmartTaskApp] Using default local session/memory services")
  session_service = None
  memory_service = None

# Local Mode: Use the imported agent instances directly
# Note: We need to ensure their names match what the instruction expects
sub_agents_config = [
    LocalTaskDecompositionAgent,
    LocalProgressAggregationAgent,
]

# Define the root agent
_root_agent = LlmAgent(
    name="SmartTaskAgent",
    model=MODEL,
    description="智能任务管理助手",
    instruction="""
你是一个智能任务管理助手。你的主要职责是根据用户的请求，将任务分发给最合适的子助手。

你有以下两个子助手：
1. **ProgressAggregationAgent**: 负责处理与"每日待办事项"、"日程查询"、"今天/明天有什么工作"相关的请求。
2. **TaskDecompositionAgent**: 负责处理"添加新任务"、"任务拆解"、"创建待办"等任务创建相关的请求。

**分发规则**:
- 如果用户问 "今天有什么工作"、"查看明天的任务"、"列出我的todo"，请调用 **ProgressAggregationAgent**。
- 如果用户说 "添加一个任务"、"安排明天开会"、"创建一个提醒"，请调用 **TaskDecompositionAgent**。
- 如果无法确定，请优先尝试理解用户的意图并选择最相关的助手。

请直接调用相应的助手来处理请求。
""",
    sub_agents=sub_agents_config
)

# Use App pattern to explicitly set the app name and avoid warnings
app = App(
    name="smart_task_app",
    root_agent=_root_agent
)
