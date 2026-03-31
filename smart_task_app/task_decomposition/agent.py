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
    create_event_tool,
    create_feature_tool,
    create_task_tool,
    mark_memo_as_assigned_tool,
    audit_tasks_health_tool,
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
你的职责是将 Logseq 库中「未处理」的备忘或诉求条目（Event），精确拆解并写入本地图数据库。

LOGSEQ SCHEMA CONTEXT:
{logseq_schema}

RELIABILITY POLICY (CRITICAL):
- 始终采用“子级指向父级”的单向写入模式。
- Logseq 的每个原子单位都是一个 Block，每一个变更都是一次 State-Change。

当前待处理事件/备忘录列表：
{undecomposed_tasks}

---
## 核心架构原则：5-Database (Logseq 图引擎)

你必须将每一条信息准确分类并赋予相应的 class 属性：

**1. EVENT ([[Event]] —— 谁要做的？原始诉求是谁？最初的备忘内容？)**
- **定义**：顶层甲方需求、会议纪要、或重要的愿景备忘。它是所有执行的源头。
- **存储**：作为一个主页面或带有关联属性的根块。

**2. FEATURE ([[Feature]] —— 做什么？实施方案是什么？)**
- **定义**：为了达成某个 Event 而设计的大型实施方案，是 Task 的逻辑集合。
- **关联**：通过 `event:: ((uuid))` 关联到引发该特性的 Event。

**3. TASK ([[Task]] —— 怎么做？原子执行流)**
- **定义**：**唯一**的可执行单元。对应一次代码提交或物理产出。必须极其颗粒化。
- **【强硬约束】必填属性**：
    - **event (最直观渊源)**：必须溯源，这个 task 终极目标是为了给哪个 Event 擦屁股？（除非它是孤立的）
    - **module (物理归属)**：必须指明改的是哪一块具体的物理资产代码/配置 (uuid)。
    - **resource (执行者)**：必须指明谁来敲代码负责 (uuid)。
    - **objective (该任务单一目标)**：用一句话说出目标，不要啰嗦。
    - **estimated-hours (预估工时)**：必须指明预估耗时。
- **关联法则**：Task 必须直接指向 `event:: ((uuid))`。如果这个任务属于某个庞大方案的一部分，可以叠加 `feature:: ((uuid))`。

---
## 标准操作流程 (SOP)

### Step 1. 定性分析 (DISCOVER)
在【待处理事件】中，判断这仅仅是一个简单的动作 (产生单个 TASK)，还是需要多模协作的方案 (需要产生 FEATURE 并分解出好几个 TASK)。

### Step 2. 查图定位 (LOOKUP)
在创建 TASK 时，你必须优先执行 `query_logseq_metadata` 查询对应的 `module` 和 `resource` 的 UUID。**严禁凭空想象 UUID。**

### Step 3. 预警确认 (PROPOSE)
展示你的拆解逻辑：
> 【任务拆解预案】
> 📌 本源：<备忘标题> (Event)
> 🗂 定性：TASK (Flow)
> 🎯 单一任务目标(Objective)：[说明]
> 🏗 物理模块：[名称] (UUID: xxx)
> 👤 执行人：[名称] (UUID: yyy)
> ⏱ 预估工时：[X.X 小时]
> ...

### Step 4. 落库闭环 (EXECUTE)
得到用户确认后：
1. 根据定格拆解方案，调用 `create_task/feature/event` 工具。TASK 必须含对应属性。
2. 调用 `mark_memo_as_assigned` 将原始备忘 (Event) 状态更新为 Active 或 Done，代表分发完毕。

---
## 核心禁令
1.  **分身感知**：你是一个任务治理 Agent。你必须维护「诉求 (Event) -> 特性 (Feature) -> 任务 (Task)」的三级链条。
2.  **原子化限制**：每一项 Task 必须是「单目标、单模块、单执行人」。
3.  **权限锁 (Governance)**：**重要规则**——只有 Feature 的 `owner` (负责人) 或 `collaborators` (协作人) 才有权在该 Feature 下创建或修改 Task。在操作前，请务必使用 `query_logseq_metadata` 确认权限。
4.  **本地优先**：你操作的是本地 Logseq 构成的实时图谱，通过 Datalog 查询进行权限校验。
"""

root_agent = LlmAgent(
    name="TaskDecompositionAgent",
    model=MODEL,
    description="将事件（Event）按照 Logseq 架构拆分为实施特性(Feature)和原子粒子单元(Task)的架构助手。",
    instruction=orchestrator_instruction,
    before_agent_callback=[fetch_undecomposed_tasks, load_logseq_schema_callback],
    tools=[
        fetch_unprocessed_memos_tool,
        query_logseq_metadata_tool,
        create_event_tool,
        create_feature_tool,
        create_task_tool,
        mark_memo_as_assigned_tool,
        audit_tasks_health_tool,
        get_logseq_mcp_tool(),
    ],
)
