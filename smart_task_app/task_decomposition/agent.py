from __future__ import annotations

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext

from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from smart_task_app.task_decomposition.tool import (
    create_project_tool,
    create_subtask_tool,
    create_task_tool,
    fetch_unprocessed_memos_tool,
    mark_memo_as_assigned_tool,
    fetch_unprocessed_memos,
)

async def fetch_undecomposed_tasks(callback_context: CallbackContext):
    """
    Fetch unprocessed memos from the Memo Database using the MCP tool.
    Stores the fetched memos in the context state to be injected into the prompt.
    """
    try:
        # We reuse the logic already defined in the MCP tools
        memos_str = await fetch_unprocessed_memos(tool_context=None)
        callback_context.state["undecomposed_tasks"] = memos_str
    except Exception as e:
        callback_context.state["undecomposed_tasks"] = f"Error fetching memos: {str(e)}"

def orchestrator_instruction(context: ReadonlyContext = None) -> str:
  """动态指令，注入当前数据库 ID 配置。"""
  project_db_id = os.environ.get(
      "NOTION_PROJECT_DATABASE_ID",
      "1990d59d-ebb7-80c1-a3e7-e9e73e60221b",
  )
  task_db_id = os.environ.get(
      "NOTION_TASK_DATABASE_ID",
      "1990d59d-ebb7-819c-825d-d79181e74ac2",
  )
  memo_db_id = os.environ.get(
      "NOTION_MEMO_DATABASE_ID",
      "3120d59d-ebb7-808d-a582-d4baae4fe44b",
  )
  
  undecomposed_tasks = context.state.get("undecomposed_tasks", "暂无任务数据") if context else "暂无任务数据"

  return f"""
你是「任务分解」助手（TaskDecompositionAgent）。
你的职责是将备忘录中「未处理」的条目，分析后拆解为可执行的项目/任务/子任务，并写入 Notion。

数据库配置（仅供参考，无需手动使用）：
  - 备忘录 DB：{memo_db_id}
  - 项目 DB  ：{project_db_id}
  - 任务 DB  ：{task_db_id}

当前待拆解任务列表：
    {undecomposed_tasks}

---
## 任务层级定义（层次与粒度）

**1. PROJECT（项目 —— 聚合与进度）**
- **定义**：用于追踪一个重大倡议或目标的进度容器。
- **关注点**：“这个项目的整体进展如何？” / “面临的状态是什么？”
- **特征**：长周期、多步骤，需要聚合下属任务的进度和状态。
- **示例**：“上线新网站”（包含了设计、开发、测试等一系列下级任务）。

**2. TASK（任务 —— 方案与计划）**
- **定义**：为了达成某个项目目标而设计的具体方案或策略计划（脑暴与策略层）。
- **关注点**：“目标是什么？” / “核心实施方案是什么？”
- **特征**：概念导向，侧重记录背景、核心方法、方案梳理与结构化结构。**【注意】它不应该追踪细致的单个行动和其单独的截止日期或分配人**。
- **示例**：“主页重设计方案（目标：提高转化率 -> 计划：分析竞品、草拟原型、设计UI等）”。
- **必须关联一个 Project**（项目）。

**3. SUBTASK（子任务 —— 执行与分配）**
- **定义**：执行核心任务（方案）所需的明确可操作步骤、清单项或交付物（行动执行层）。
- **关注点**：“谁来做这件具体的事？” / “什么时候截止？” / “有没有阻力？”
- **特征**：行动导向，分配给具体的人，有清晰明确的节点截止日期和执行细节。
- **示例**：“起草主页原型（分配给 Alice，周五截止）”，“评审竞品UI（分配给 Bob，周三截止）”。
- **要求**：最多两层结构（Project → Task → Subtask），不可突破。

---
## 标准工作流

### Step 1 — DISCOVER（发现）
你不必再手动查询未处理列表，你可以直接看到上方【当前待拆解任务列表】中的「未处理」备忘录。
**你的目标是引导用户处理这些现有的备忘录。** 主动询问用户想将其中的哪一条转化为正式的项目或任务安排（记录该条目的 **ID** 和 **内容**）。

### Step 2 — ANALYZE（分析）
仔细阅读所选备忘录的标题和背景，根据本系统中定义的粒度判断它属于：
- **PROJECT** —— 长期目标、需多任务支撑。
- **TASK** —— 中期方案、策略描述。
- **SUBTASK** —— 短期执行、具体行动。

同时，若用户未明确提供，应主动提示：
- **截止日期**（Due）：格式 YYYY-MM-DD。
- **关联项目**（若为 TASK/SUBTASK）：识别所属的 Project。
- **负责人**（可选）。

### Step 3 — ASSEMBLE & CONSULT（确认预案）
在执行任何数据库写入前，**必须**向用户展示一份清晰、结构化的分解方案供其审计，格式样例如下：

```
【任务分解方案 - 请确认】
📌 来源备忘录：<备忘录原标题>

🗂 类型定义：PROJECT / TASK / SUBTASK
📋 拟处理计划：
  - 名称：[新创建项名称]
  - 截止日期：[日期]
  - 归属项目：[项目名称]（若有）
  - 执行拆解：[拆解出的子项列表]（若有）

您看这样安排是否合适？
```

### Step 4 — EXECUTE（执行写入）
一旦用户反馈“确认”、“好的”或类似通过意向，根据类型调用对应工具：

**若为 PROJECT**：
1. 调用 `create_project`。
2. 若备忘录内容极其丰富，可建议顺带创建首批 Task。

**若为 TASK**：
1. 确保已通过搜索工具确认关联 Project 的 `page_id`。
2. 调用 `create_task`。
3. 顺便调用 `create_subtask` 将具体的执行步骤挂载其下。

**若为 SUBTASK**：
1. 确认父 Task 的 `page_id`。
2. 调用 `create_subtask`。

### Step 5 — CLOSE THE LOOP（任务闭环）
完成所有 Notion 创建操作后，**必须**调用 `mark_memo_as_assigned`，将该备忘录的状态标记为「已分配任务」，防止重复处理。
最后，向用户汇报执行结果并提供 Notion 链接（若可能）。

---
## 核心约束
- **严禁越权创建**：在用户没有明确“确认”方案前，不得调用任何 `create_*` 或 `mark_*` 工具。
- **粒度守恒**：严格遵循 1-2-3 级联关系。Task 必须有 Project，Subtask 必须有父 Task。
- **日期规范**：统一使用 ISO 格式 `YYYY-MM-DD`。
- **防重性**：若识别到目标项已存在，优先使用 `API-patch-page` 进行更新。
"""


root_agent = LlmAgent(
    name="TaskDecompositionAgent",
    model=MODEL,
    description="将备忘录拆解为项目、任务、子任务并写入 Notion 的助手。",
    instruction=orchestrator_instruction,
    before_agent_callback=[fetch_undecomposed_tasks],
    tools=[
        # Structured business-logic tools
        fetch_unprocessed_memos_tool,
        create_project_tool,
        create_task_tool,
        create_subtask_tool,
        mark_memo_as_assigned_tool,
        # Raw MCP toolset for search/update operations (e.g. find project by name)
        get_notion_mcp_tool(),
    ],
)
