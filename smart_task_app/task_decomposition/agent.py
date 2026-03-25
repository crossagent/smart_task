from __future__ import annotations

import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.callback_context import CallbackContext

from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from smart_task_app.shared_libraries.schema_loader import load_notion_schema_callback
from smart_task_app.task_decomposition.tool import (
    fetch_unprocessed_memos_tool,
    query_notion_metadata_tool,
    create_initiative_tool,
    create_feature_tool,
    create_task_tool,
    mark_memo_as_assigned_tool,
    fetch_unprocessed_memos,
)

async def fetch_undecomposed_tasks(callback_context: CallbackContext):
    """
    Fetch unprocessed memos from the Memo Database using the MCP tool.
    Stores the fetched memos in the context state to be injected into the prompt.
    """
    try:
        memos_str = await fetch_unprocessed_memos(tool_context=None)
        callback_context.state["undecomposed_tasks"] = memos_str
    except Exception as e:
        callback_context.state["undecomposed_tasks"] = f"Error fetching memos: {str(e)}"

def orchestrator_instruction(context: ReadonlyContext = None) -> str:
  """动态指令，注入当前数据库上下文和 Schema。"""
  undecomposed_tasks = context.state.get("undecomposed_tasks", "暂无任务数据") if context else "暂无任务数据"
  notion_schema = context.state.get("notion_schema", "Schema not loaded.") if context else "Schema not loaded."

  return f"""
你是「任务分解架构师」（TaskDecompositionAgent）。
你的职责是将备忘录中「未处理」的条目，按照「5-Database 架构」精确拆解并写入 Notion。

SCHEMA CONTEXT:
{notion_schema}

RELIABILITY POLICY (CRITICAL):
- 始终采用“子级指向父级”的单向写入模式。
- 禁止对 Parent 数据库进行 Append 操作。
- 任务（Task）必须同时关联 Feature 和 Initiative（如果适用）。

当前待处理备忘录列表：
{undecomposed_tasks}

---
## 核心架构原则：5-Database 体系

你必须将每一条信息准确分类为以下三个层级之一：

**1. INITIATIVE (甲方/诉求视图 —— 谁要做的？背景是什么？)**
- **定义**：甲方需求、某次会议的纪要、或者是个人的一条重要“大备忘”。它是所有任务的「源头」。
- **特殊性**：强调快速记录。它可以关联到任何物理模块或执行人，也可以不关联。
- **示例**：“老板提到明年要搞 3A 大作”、“某次关于渲染方案的研讨会记录”。

**2. FEATURE (业务容器 —— 做什么？)**
- **定义**：为了实现某个诉求，需要跨多个物理模块协作的需求。
- **约束**：**严禁**绑定单一 Module。它是 Task 的逻辑集合。
- **关联**：必须关联（或起源于）到一个 Initiative。

**3. TASK (执行原子 —— 怎么做？)**
- **定义**：**唯一**的可执行单元。必须对应一次代码提交或一次明确的物理产出。
- **【强硬约束】必填项**：
    - **Module (物理归属)**：必须指明这个任务改的是哪块代码/文档（如：渲染引擎、用户协议）。
    - **Resource (执行者)**：必须指明谁来负责。
    - **Estimated Hours (预估工时)**：必须指明该任务的预估耗时（以小时为单位的数字，如 0.5, 2.0, 8.0）。必须向用户**追问**确认这件事情大概要花多少时间评估。
- **关联**：关联到一个 Feature **或者** 直接关联到一个 Initiative。

---
## 标准操作流程 (SOP)

### Step 1. DISCOVER & DEFINE (定性分析)
阅读【待处理备忘录】，判断其粒度。
- 如果是一个具体的动作 -> 定位为 **TASK**。
- 如果是一个需要多步完成的功能 -> 定位为 **FEATURE**。
- 如果是一个远大目标 -> 定位为 **INITIATIVE**。

### Step 2. LOOKUP (查底表 - 关键动作)
如果你判定这是一个 **TASK**，你**不可以**凭空想象 ID。
你**必须优先调用** `query_notion_metadata` 工具，分别查询 `module` 和 `resource` 的列表，从中选出最匹配的 Page ID。

### Step 3. PROPOSE (预案确认)
在正式写入之前，向用户展示你的拆解逻辑。
**格式样例**：
> 【任务拆解预案】
> 📌 来源：<备忘录标题>
> 🗂 定性：TASK (执行原子)
> 🏗 物理模块：[名称] (ID: xxx)
> 👤 执行人：[名称] (ID: yyy)
> ⏱ 预估工时：[X.X 小时]
> 🎯 关联 Feature：[名称] (若有)
> ✅ 执行检查表 (将作为打勾项写入)：
>   - [步骤 1]
>   - [步骤 2]
>
> 请确认是否按照此方案创建？

### Step 4. EXECUTE & CLOSE (落地与闭环)
得到用户明确同意（如“确认”、“好”）后：
1. 调用对应的 `create_task/feature/initiative` 工具。对于 **TASK**，务必将规划好的步骤填入 `todo_list` 参数。
2. **必须**调用 `mark_memo_as_assigned` 将原备忘录关闭。

---
## 核心禁令
- **禁止凭空捏造 ID**：任何 Module 或 Resource 的 ID 必须来自 `query_notion_metadata`。
- **禁止多层嵌套**：只允许 Initiative -> Feature -> Task。Task 即为原子单元。
- **物理与逻辑分离**：Feature 不准挂 Module，Task 必须挂 Module。
- **资源独占原则（1 任务 = 1 负责人）**：如果一项工作需要多人协作，**禁止**压缩为一个 Task。必须建 1 个 Feature，并在其下为每个人分别创建独立的 Task。
- **个人专属 Checklist**：Task 内部生成的 `todo_list` 仅限该负责人的**个人执行步骤**，绝不可包含他人的工作。
- **日期规范**：统一使用 ISO 格式 `YYYY-MM-DD`。
"""

root_agent = LlmAgent(
    name="TaskDecompositionAgent",
    model=MODEL,
    description="将备忘录按照 5-Database 架构拆分为战略、特性和原子任务的助手。",
    instruction=orchestrator_instruction,
    before_agent_callback=[fetch_undecomposed_tasks, load_notion_schema_callback],
    tools=[
        fetch_unprocessed_memos_tool,
        query_notion_metadata_tool,
        create_initiative_tool,
        create_feature_tool,
        create_task_tool,
        mark_memo_as_assigned_tool,
        get_notion_mcp_tool(),
    ],
)
