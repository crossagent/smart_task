import os
import sys
from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent, AGENT_CARD_WELL_KNOWN_PATH
from google.adk.apps import App

# Import local implementations of sub-agents
# We use relative imports to avoid hardcoding the package name 'smart_task_app' to be robust
from .remote_a2a.new_task.agent import root_agent as LocalAddTaskOrchestrator
from .remote_a2a.daily_todo.agent import root_agent as LocalDailyTodoAgent

# Determine mode: Default to Local (False) if not explicitly set to "true"
IS_REMOTE_MODE = os.environ.get("REMOTE_AGENTS", "false").lower() == "true"

print(f"[SmartTaskApp] Loading in {'REMOTE' if IS_REMOTE_MODE else 'LOCAL'} mode.")

if IS_REMOTE_MODE:
    # Remote Mode: Use RemoteA2aAgent to connect to separate processes
    sub_agents_config = [
        RemoteA2aAgent(
            name="AddTaskOrchestrator", 
            agent_card=f"http://localhost:28001/a2a/new_task{AGENT_CARD_WELL_KNOWN_PATH}"
        ),
        RemoteA2aAgent(
            name="DailyTodoAgent", 
            agent_card=f"http://localhost:28001/a2a/daily_todo{AGENT_CARD_WELL_KNOWN_PATH}"
        )
    ]
else:
    # Local Mode: Use the imported agent instances directly
    # Note: We need to ensure their names match what the instruction expects
    # The imported agents already have names "AddTaskOrchestrator" and "DailyTodoAgent"
    sub_agents_config = [
        LocalAddTaskOrchestrator,
        LocalDailyTodoAgent
    ]

# Define the root agent
_root_agent = LlmAgent(
    name="SmartTaskAgent",
    model="gemini-2.5-flash",
    description="智能任务管理助手",
    instruction="""
你是一个智能任务管理助手。你的主要职责是根据用户的请求，将任务分发给最合适的子助手。

你有以下两个子助手：
1. **DailyTodoAgent**: 负责处理与"每日待办事项"、"日程查询"、"今天/明天有什么工作"相关的请求。
2. **AddTaskOrchestrator**: 负责处理"添加新任务"、"安排会议"、"创建待办"等任务创建相关的请求。

**分发规则**:
- 如果用户问 "今天有什么工作"、"查看明天的任务"、"列出我的todo"，请调用 **DailyTodoAgent**。
- 如果用户说 "添加一个任务"、"安排明天开会"、"创建一个提醒"，请调用 **AddTaskOrchestrator**。
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
