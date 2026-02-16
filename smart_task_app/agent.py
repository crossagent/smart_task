import os
import sys
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.apps import App
from .shared_libraries.constants import MODEL

# Import local implementations of sub-agents
# We use relative imports to avoid hardcoding the package name 'smart_task_app' to be robust
from .remote_a2a.task_decomposition.agent import root_agent as LocalTaskDecompositionAgent
from .remote_a2a.progress_aggregation.agent import root_agent as LocalProgressAggregationAgent
from .remote_a2a.experience_agent.agent import root_agent as LocalExperienceAgent

# Determine mode: Default to Local (False) if not explicitly set to "true"
IS_REMOTE_MODE = os.environ.get("REMOTE_AGENTS", "false").lower() == "true"

print(f"[SmartTaskApp] Loading in {'REMOTE' if IS_REMOTE_MODE else 'LOCAL'} mode.")

if IS_REMOTE_MODE:
    # Remote Mode: Use RemoteA2aAgent to connect to separate processes
    sub_agents_config = [
        RemoteA2aAgent(
            name="TaskDecompositionAgent", 
            agent_card=f"http://localhost:28001/a2a/task_decomposition{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
        RemoteA2aAgent(
            name="ProgressAggregationAgent", 
            agent_card=f"http://localhost:28001/a2a/progress_aggregation{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
        RemoteA2aAgent(
            name="ExperienceAgent",
            agent_card=f"http://localhost:28001/a2a/experience_agent{AGENT_CARD_WELL_KNOWN_PATH}"
        )
    ]
else:
    # Local Mode: Use the imported agent instances directly
    # Note: We need to ensure their names match what the instruction expects
    sub_agents_config = [
        LocalTaskDecompositionAgent,
        LocalProgressAggregationAgent,
        LocalExperienceAgent
    ]

# Define the root agent
_root_agent = LlmAgent(
    name="SmartTaskAgent",
    model=MODEL,
    description="智能任务管理助手",
    instruction="""
你是一个智能任务管理助手。你的主要职责是根据用户的请求，将任务分发给最合适的子助手。

你有以下三个子助手：
1. **ProgressAggregationAgent**: 负责处理与"每日待办事项"、"日程查询"、"今天/明天有什么工作"相关的请求。
2. **TaskDecompositionAgent**: 负责处理"添加新任务"、"任务拆解"、"创建待办"等任务创建相关的请求。
3. **ExperienceAgent**: 负责查找历史参考方案和保存成功经验。

**分发规则**:
- 如果用户问 "今天有什么工作"、"查看明天的任务"、"列出我的todo"，请调用 **ProgressAggregationAgent**。
- 如果用户说 "添加一个任务"、"安排明天开会"、"创建一个提醒"，请调用 **TaskDecompositionAgent**。
- 如果用户问 "有类似的案例吗"、"历史上怎么解决的"、"查找参考方案"、"保存这个经验"，请调用 **ExperienceAgent**。
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
