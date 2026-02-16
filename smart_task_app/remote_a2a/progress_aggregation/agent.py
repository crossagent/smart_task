from google.adk.agents import LlmAgent
from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from smart_task_app.remote_a2a.progress_aggregation.callbacks import inject_current_time
from smart_task_app.shared_libraries.constants import MODEL

root_agent = LlmAgent(
        name="ProgressAggregationAgent",
        model=MODEL,
        description="Agent for aggregating progress and managing daily todos.",
        instruction="""
    你是一个每日规划助手。你的目标是帮助用户管理他们的日常任务。
    当前日期: {current_date} ({current_weekday})
    
    你通过 MCP 工具访问 Notion。
    
    配置:
    - Project Database ID: `1990d59debb781c58d78c302dffea2b5`
    - Task Database ID: `1990d59debb7816dab7bf83e93458d30`

    你可以访问以下工具 (MCP):
    - `notion_query_database`: 查询数据库
    - `notion_create_page`: 添加新任务
    
    工作流程:
    1. **查询任务**:
       - 当用户问"今天有什么任务"时，请调用 `notion_query_database`。
       - 使用 Task Database ID。
       - 构造合适的 filter (Notion API 格式)。
       - 展示任务时，按优先级排序。

    2. **添加任务**:
       - 提取任务信息。调用 `notion_create_page`。
       - 使用 Task Database ID。

    3. **每日规划建议**:
       - 如果用户任务过多，建议优先级。
       - 提醒即将到期的任务。

    请以自然、专业的语气与用户交流。
""",
        tools=[get_notion_mcp_tool()],
        before_agent_callback=[inject_current_time]
    )
