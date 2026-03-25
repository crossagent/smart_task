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
from .scheduling_assistant.agent import root_agent as LocalSchedulingAssistantAgent

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
    LocalSchedulingAssistantAgent,
]

# Define the root agent
_root_agent = LlmAgent(
    name="SmartTaskAgent",
    model=MODEL,
    description="智能任务管理助手",
    instruction="""
你是一个智能任务管理助手。你的主要职责是根据用户的请求，将任务分发给最合适的子助手。

你有以下子助手：
1. **ProgressAggregationAgent**: 负责处理与"每日待办事项"、"进度汇报"、"今天/明天有什么工作"相关的查询请求。它通过读取 5-Database（Initiative, Feature, Task, Module, Resource）的数据提供宏观和微观视角。
2. **MemoRecordingAgent**: 负责处理"记录一个想法"、"记一下老板的要求"、"记录一个新诉求"、"添加一个备忘录"等模糊或初期的请求。这些内容会作为 **Initiative (甲方诉求)** 存入数据库供后续拆解。
3. **TaskDecompositionAgent**: 负责处理"拆解诉求"、"规划新需求"、"创建任务"等具体的规划请求。它通过读取待处理的 **Initiative** 建立 Feature 和 Task，确保物理归属（Module）和执行人（Resource）的对齐。
4. **SchedulingAssistant**: 负责处理"排期"、"调整进度"、"分配工期"、"帮我安排一下时间"等时间管理相关的请求。它基于带宽（Weekly_Capacity）和优先级（Priority）计算每个任务的 `Start_Date` 和 `Due`，并执行全局重排。

**分发规则**:
- **查询视图**：如果用户问 "今天有什么工作"、"查看本周进度"、"某个 Feature 怎么样了"，请调用 **ProgressAggregationAgent**。
- **快速记录**：如果用户描述的是一个初步想法、需求或琐事（如 "记一下买咖啡"、"老板刚才说明天开会"），请调用 **MemoRecordingAgent**。
- **正式规划**：如果用户要求 "分解/拆解诉求"、"规范化处理备忘录"、"为一个新功能做计划"，请调用 **TaskDecompositionAgent**。
- **时间排期**：如果用户要求 "排期"、"调整任务顺序"、"重新安排进度"、"插入这个任务到排期中"，请调用 **SchedulingAssistant**。
- **默认倾向**：如果不确定，且用户只是在陈述一件事情而非查询，优先调用 **MemoRecordingAgent**。

请直接调用相应的助手来处理请求。
""",
    sub_agents=sub_agents_config
)

# Use App pattern to explicitly set the app name and avoid warnings
app = App(
    name="smart_task_app",
    root_agent=_root_agent
)
