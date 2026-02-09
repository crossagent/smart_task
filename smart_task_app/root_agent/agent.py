import os
import sys
from google.adk.agents import LlmAgent

# Try to import local agents
try:
    from smart_task_app.new_task.agent import new_task_agent
except ImportError:
    new_task_agent = None

try:
    from smart_task_app.daily_todo.agent import daily_todo_agent
except ImportError:
    daily_todo_agent = None

# Try to import RemoteA2aAgent (available in newer ADK versions)
try:
    from google.adk.a2a.agents import RemoteA2aAgent
except ImportError:
    RemoteA2aAgent = None

def create_root_agent():
    sub_agents = []
    
    # Mode A: A2A (via Environment Variable)
    if os.getenv("ENABLE_A2A") == "true":
        print("Using A2A Remote Connection")
        if not RemoteA2aAgent:
             raise ImportError("RemoteA2aAgent not found in google.adk.a2a.agents")
             
        sub_agents = [
            RemoteA2aAgent(
                name="AddTaskOrchestrator", 
                url="http://localhost:8000/a2a/AddTaskOrchestrator" 
            ),
            RemoteA2aAgent(
                name="DailyTodoAgent", 
                url="http://localhost:8000/a2a/DailyTodoAgent" 
            )
        ]
        
    # Mode B: Local Import
    else:
        print("Using Local Import Connection")
        if new_task_agent:
            sub_agents.append(new_task_agent)
        else:
            print("Warning: new_task_agent not found locally")
            
        if daily_todo_agent:
            sub_agents.append(daily_todo_agent)
        else:
            print("Warning: daily_todo_agent not found locally")

    return LlmAgent(
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
        sub_agents=sub_agents
    )

agent = create_root_agent()
