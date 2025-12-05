from google.adk.agents import LlmAgent
from agents.tools.notion import get_database_schema, query_database, add_task_to_database
from agents.tools.time import get_current_datetime

def DailyTodoAgent(name: str = "DailyTodoAgent") -> LlmAgent:
    """
    DailyTodoAgent - 每日待办事项管理助手
    
    职责:
    - 查询Notion中的待办事项
    - 添加新任务到Notion
    - 协助用户进行每日规划
    """
    return LlmAgent(
        name=name,
        model="gemini-2.5-flash",
        description="每日待办事项管理助手",
        instruction="""
你是一个每日规划助手。你的目标是帮助用户管理他们的日常任务。

你可以访问以下工具:
- get_current_datetime(): 获取当前日期和时间
- get_database_schema(database_name): 查看数据库结构(Project或Task)
- query_database(query): 使用SQL-like语法查询数据
- add_task_to_database(title, status, priority, due_date): 添加新任务

工作流程:
1. **初始化**:
   - 总是首先调用 `get_current_datetime()` 获取当前日期。

2. **查询任务**:
   - 当用户问"今天有什么任务"时，使用当前日期作为过滤条件。
   - 示例查询: "SELECT * FROM Task WHERE due_date = '2025-12-05' AND status != 'Done'"
   - 展示任务时，按优先级排序。

3. **添加任务**:
   - 提取任务信息。如果用户说"明天"，基于当前日期计算具体日期。
   - 调用 `add_task_to_database`。

4. **每日规划建议**:
   - 如果用户任务过多，建议优先级。
   - 提醒即将到期的任务。

请以自然、专业的语气与用户交流。
""",
        tools=[get_current_datetime, get_database_schema, query_database, add_task_to_database]
    )

daily_todo_agent = DailyTodoAgent()
