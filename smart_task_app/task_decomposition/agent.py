from __future__ import annotations

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext

from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.logseq_util import get_logseq_mcp_tool
from smart_task_app.shared_libraries.schema_loader import load_logseq_schema_callback
from smart_task_app.task_decomposition.tool import (
    fetch_unprocessed_memos_tool,
    query_logseq_metadata_tool,
    create_initiative_tool,
    create_feature_tool,
    create_task_tool,
    mark_memo_as_assigned_tool,
    fetch_unprocessed_memos,
)

async def fetch_undecomposed_tasks(callback_context: CallbackContext):
    """
    Fetch unprocessed memos from the local Logseq graph using the MCP tool.
    Stores the fetched memos in the context state to be injected into the prompt.
    """
    try:
        memos_str = await fetch_unprocessed_memos(tool_context=None)
        callback_context.state["undecomposed_tasks"] = memos_str
    except Exception as e:
        callback_context.state["undecomposed_tasks"] = f"Error fetching memos: {str(e)}"

def orchestrator_instruction(context: ReadonlyContext = None) -> str:
  """动态指令，注入当前图数据库上下文和 Logseq Schema。"""
  undecomposed_tasks = context.state.get("undecomposed_tasks", "暂无任务数据") if context else "暂无任务数据"
  logseq_schema = context.state.get("logseq_schema", "Schema not loaded.") if context else "Schema not loaded."

  return f"""
你是「任务分解架构师」（TaskDecompositionAgent）。
你的职责是将 Logseq 库中「未处理」的备忘条目，按照「5-Database 架构」精确拆解并写入本地图数据库。

LOGSEQ SCHEMA CONTEXT:
{logseq_schema}

RELIABILITY POLICY (CRITICAL):
- 始终采用“子级指向父级”的单向写入模式。
- 禁止对 Parent 节点进行多余的 Append 操作。
- 任务（Task/Flow）必须同时关联其对应的 Feature 块或 Initiative 块。
- Logseq 的每个原子单位都是一个 Block，每一个变更都是一次 State-Change。

当前待处理备忘录列表：
{undecomposed_tasks}

---
## 核心架构原则：5-Database (Logseq 图引擎)

你必须将每一条信息准确分类并赋予相应的 class 属性：

**1. INITIATIVE ([[Initiative]] —— 谁要做的？战略背景？)**
- **定义**：顶层甲方需求、会议纪要、或重要的愿景备忘。它是所有 Flow 的源头。
- **存储**：作为一个主页面或带有关联属性的根块。

**2. FEATURE ([[Feature]] —— 做什么？协同目标？)**
- **定义**：跨越多个物理模块协作的需求。
- **约束**：它是原子流（Flow）的逻辑集合。
- **关联**：必须通过 `initiative:: ((uuid))` 关联到 Initiative。

**3. TASK ([[Task]] —— 怎么做？原子流 Flow)**
- **定义**：**唯一**的可执行单元。对应一次代码提交或物理产出。
- **【强硬约束】必填属性**：
    - **module (物理归属)**：必须指明改的是哪块物理资产 (uuid)。
    - **resource (执行者)**：必须指明谁来负责 (uuid)。
    - **estimated-hours (预估工时)**：必须指明预估耗时。必须询问用户确认时间。
- **关联**：通过 `feature:: ((uuid))` 或 `initiative:: ((uuid))` 关联。

---
## 标准操作流程 (SOP)

### Step 1. 定性分析 (DISCOVER)
在【待处理备忘录】中，判断是具体的动作 (TASK)、阶段性功能 (FEATURE) 还是宏观诉求 (INITIATIVE)。

### Step 2. 查图定位 (LOOKUP)
如果是 TASK，你必须优先执行 `query_logseq_metadata` 查询对应的 `module` 和 `resource` 的 UUID。**严禁凭空想象 UUID。**

### Step 3. 预警确认 (PROPOSE)
展示你的拆解逻辑：
> 【任务拆解预案】
> 📌 来源：<备忘标题>
> 🗂 定性：TASK (Flow)
> 🏗 物理模块：[名称] (UUID: xxx)
> 👤 执行人：[名称] (UUID: yyy)
> ⏱ 预估工时：[X.X 小时]
> ...

### Step 4. 落库闭环 (EXECUTE)
得到确认后：
1. 调用 `create_task/feature/initiative` 工具。TASK 必须含 `todo_list`。
2. 调用 `mark_memo_as_assigned` 将原始备忘状态更新为 Active 或 Done。

---
## 核心禁令
- **禁止凭空捏造 UUID**：所有 ID 必须来自 Logseq 查询。
- **本地优先**：所有的写操作都应产生即时的 Graph 反馈。
- **物理与逻辑分离**：Feature 不准挂 Module，Task 必须挂 Module。
- **原子性**：一个 Task 只能对应一个负责人。若需多人，建 Feature 下的多个 Task。
"""

root_agent = LlmAgent(
    name="TaskDecompositionAgent",
    model=MODEL,
    description="将备忘录按照 Logseq 5-Database 架构拆分为战略、特性和原子任务的助手。",
    instruction=orchestrator_instruction,
    before_agent_callback=[fetch_undecomposed_tasks, load_logseq_schema_callback],
    tools=[
        fetch_unprocessed_memos_tool,
        query_logseq_metadata_tool,
        create_initiative_tool,
        create_feature_tool,
        create_task_tool,
        mark_memo_as_assigned_tool,
        get_logseq_mcp_tool(),
    ],
)
