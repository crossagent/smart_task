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
from .memo_recording.agent import root_agent as LocalMemoRecordingAgent

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
    LocalMemoRecordingAgent,
]

# Define the root agent
_root_agent = LlmAgent(
    name="SmartTaskAgent",
    model=MODEL,
    description="智能任务管理助手",
    instruction="""
你是一个智能任务管理助手。你的主要职责是根据用户的请求，将任务分发给最合适的子助手。

你有以下子助手：
1. **ProgressAggregationAgent**: 负责处理与"每日待办事项"、"日程查询"、"今天/明天有什么工作"相关的请求。
2. **MemoRecordingAgent**: 负责处理"记录一个想法"、"老板说要..."、"添加一个备忘录"、"记一个新需求"等模糊或初期的任务录入请求。
3. **TaskDecompositionAgent**: 负责处理"拆解备忘录"、"细化需求"、"创建待办"等具体的任务规划和层级拆分请求。

**分发规则**:
- 如果用户问 "今天有什么工作"、"查看明天的任务"、"列出我的todo"，请调用 **ProgressAggregationAgent**。
- 如果用户描述的是一个想法、需求或安排，但**没有提及明确的截止日期（deadline）**，请调用 **MemoRecordingAgent** 先记录下来。
- 如果用户描述的内容**包含明确的截止日期或时间要求**（如"下周五前完成"、"明天截止"、"三天内"），且需要拆解规划，请调用 **TaskDecompositionAgent**。
- 如果用户明确说 "分解任务"、"将备忘录拆分为项目和任务"，请调用 **TaskDecompositionAgent**。
- 如果无法确定，请优先尝试理解用户的意图并选择最相关的助手。默认倾向于 **MemoRecordingAgent**，除非有明确的 deadline。

请直接调用相应的助手来处理请求。
""",
    sub_agents=sub_agents_config
)

# Use App pattern to explicitly set the app name and avoid warnings
app = App(
    name="smart_task_app",
    root_agent=_root_agent
)
