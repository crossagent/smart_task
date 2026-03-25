from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from smart_task_app.progress_aggregation.callbacks import inject_current_time
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.schema_loader import load_notion_schema_callback

def get_progress_aggregation_instruction(context=None):
    notion_schema = context.state.get("notion_schema", "Schema not loaded.") if context else "Schema not loaded."
    current_date = context.state.get("current_date", "Unknown") if context else "Unknown"
    current_weekday = context.state.get("current_weekday", "Unknown") if context else "Unknown"

    return f"""
    你是一个「观测制」进度管理助手。你的目标是基于 Notion 5-Database 架构（Initiative, Feature, Task, Module, Resource）为用户提供客观的进度反馈。
    当前日期: {current_date} ({current_weekday})
    
    SCHEMA CONTEXT:
    {notion_schema}

    工作流程:
    1. **多视角查询**:
       - **Resource 视角**：当问"我今天干嘛"时，过滤 Task 库中关联用户 Resource ID 且状态不为 Done 的项。
       - **Module 视角**：当问"某个模块怎么样"时，通过 Module ID 过滤相关的 Task。
       - **Feature 视角**：当问"某个需求进度"时，查看关联该 Feature 的 Task 完成比例。
       - **Initiative 视角**：提供全局战略状态。

    2. **客观分析**:
       - 进度不应仅看百分比，应观察是否有 Blocked 状态的任务。
       - 提醒即将到期的 Task。

    请以专业、深刻的语气汇报进度。记住：你的汇报是基于客观数据的「观测」，而不是主观的「填报」。
    """

root_agent = LlmAgent(
    name="ProgressAggregationAgent",
    model=MODEL,
    description="Agent for aggregating progress and managing daily todos.",
    instruction=get_progress_aggregation_instruction,
    tools=[get_notion_mcp_tool()],
    before_agent_callback=[inject_current_time, load_notion_schema_callback]
)
