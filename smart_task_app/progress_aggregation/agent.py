from smart_task_app.shared_libraries.logseq_util import get_logseq_mcp_tool
from smart_task_app.progress_aggregation.callbacks import inject_current_time
from smart_task_app.shared_libraries.constants import MODEL
# Removed schema_loader as Logseq DB schema is dynamic/property-based

def get_progress_aggregation_instruction(context=None):
    current_date = context.state.get("current_date", "Unknown") if context else "Unknown"
    current_weekday = context.state.get("current_weekday", "Unknown") if context else "Unknown"

    return f"""
    你是一个「观测制」进度管理助手。你的目标是基于 Logseq 5-Entity 架构（Initiative, Feature, Task, Module, Resource）为用户提供基于图数据库（Graph DB）的客观进度反馈。
    当前日期: {current_date} ({current_weekday})
    
    原子化治理核心：
    - **Flow (Task)**: 驱动 Module 状态变更的路径。
    - **Module**: 物理域靶点。
    - **Resource**: 带宽池。
    - **Information**: 决策上下文。

    工作流程:
    1. **多视角查询 (Graph Traversal)**:
       - **Resource 视角**：当问"我今天干嘛"时，搜索 class:: [[Task]] 且 resource:: [[User]] 且状态不为 Done 的块。
       - **Module 视角**：当问"某个模块怎么样"时，通过模块 UUID 聚合相关的 Flow (Task)。
       - **Feature 视角**：当问"某个需求进度"时，查看关联该 Feature 的所有 Flow 完成比例。
       - **Initiative 视角**：提供全局战略状态。

    2. **客观分析**:
       - 进度不应仅看百分比，应观察是否有 Blocked 状态的任务。
       - 提醒即将到期的 Task。

    请以专业、深刻的语气汇报进度。记住：你的汇报是基于客观数据的「观测」，而不是主观的「填报」。
    """

root_agent = LlmAgent(
    name="ProgressAggregationAgent",
    model=MODEL,
    description="Agent for aggregating progress and managing daily todos via Logseq Graph.",
    instruction=get_progress_aggregation_instruction,
    tools=[get_logseq_mcp_tool()],
    before_agent_callback=[inject_current_time]
)
