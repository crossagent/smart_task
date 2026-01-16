# Smart Task Agent Design V2

## 目标
构建一个多轮对话的智能任务管理系统，利用 ADK 的 "Agent as Tool" 能力，实现任务的自动分类、背景填充和最终确认。

## 核心架构

系统采用 **中心化编排 (Orchestrator) + 专业代理工具 (Specialist Agents as Tools)** 的模式。

### 1. 主代理 (Orchestrator Agent)
**角色**: 项目经理 / 交互接口
**职责**:
*   **意图识别与规模判断 (Sizing)**: 判断用户输入是 "Project" (宏大目标) 还是 "Task" (具体交付物)。
*   **流程控制**: 维护任务添加的标准流程 (SOP)。
*   **人机交互**: 在关键节点（如规模调整、字段确认）请求用户反馈。
*   **最终执行**: 调用工具写入 Notion 并更新每日计划。

**主要指令 (Instructions)**:
1.  接收用户输入，首先评估任务规模 (Project vs Task)。如果模糊，与用户确认。
2.  根据确定后的类型，调用对应的 **Context Agent** (ProjectAgent/TaskAgent) 填充详细字段。
3.  向用户展示完整的任务草稿（包含推断出的 Project、Priority、Due Date 等）。
4.  获得用户 `CONFIRM` 后，调用 `NotionTool` 写入。
5.  最后条用 `DailyPlanTool` 更新每日待办列表。

### 2. 领域专家代理 (Context Agents as Tools)
这些代理被封装为工具供主代理调用。每个层级一个代理，确保上下文精准。

#### A. ProjectContextAgent (Wrapper as Tool)
*   **职责**: **Goal & Context**。管理长期目标。
*   **能力**:
    *   查询 `Project` 数据库。
    *   根据输入推荐 Parent Project。
    *   提供 Project 的 "Why" (背景/目标)。
*   **工具**: `search_projects`, `get_project_context`.

#### B. TaskContextAgent (Wrapper as Tool)
*   **职责**: **Deliverable & Responsibility**。管理具体交付物。
*   **能力**:
    *   查询 `Task` 数据库。
    *   检查任务重复性 (Duplication Check)。
    *   管理任务依赖 (`dependency_task_ids`)。
*   **工具**: `search_tasks`, `get_task_details`.

#### C. SubtaskContextAgent (Wrapper as Tool)
*   **职责**: **Action Item & Execution**。管理执行步骤。
*   **能力**:
    *   将复杂 Task 分解为可执行的 Subtasks。
    *   根据历史经验推荐 Subtask 模板。
    *   查询/记录执行过程中遇到的问题 (Log)。
*   **工具**: `generate_subtasks`, `search_subtasks`.

### 3. 基础工具 (Infrastructure Tools)
由代理调用的原子能力。

#### A. NotionTool
*   `add_page_to_database(db_id, properties)`: 通用写入。
*   `query_database(db_id, filter)`: 通用查询。

#### B. DailyPlanTool
*   `update_daily_plan(task_summary)`: 将新任务加入今日/明日的规划文档。
*   `get_current_plan()`: 读取当前规划。

---

## 交互流程示例

1.  **User**: "帮我安排一下下周的 API 性能优化。"
2.  **Orchestrator**: (Sizing: 这是一个 Project 还是 Task? 似乎是 Task，但需要确认 Project)
    *   *Call*: `ProjectContextAgent.recommend_project("API 性能优化")` -> "后端架构重构 Q1"
3.  **Orchestrator**: "这属于 '后端架构重构 Q1' 吗？如果是，是一个独立的 **Task** 吗？"
4.  **User**: "是的，是一个 Task。"
5.  **Orchestrator**: (Filling Task Fields)
    *   *Call*: `TaskContextAgent.check_duplication("API 性能优化")` -> 无重复。
    *   *Call*: `SubtaskContextAgent.suggest_breakdown("API 性能优化")` -> ["分析慢查询日志", "优化 Redis 缓存", "压测"]
6.  **Orchestrator**: "建议的子任务 (Subtasks) 如下：... 是否需要调整？"
7.  **User**: "可以。直接加吧。"
8.  **Orchestrator**: 
    *   *Call*: `NotionTool.create_task_with_subtasks(...)`
    *   *Call*: `DailyPlanTool.update_plan(...)`

## 关键字段填充策略 (Field Filling)

*   **Project**: 由 `ProjectContextAgent` 根据语义搜索推荐。
*   **Assignee**: 默认当前用户，或由 `TaskContextAgent` 根据过往类似任务推断。
*   **Subtasks**: 如果任务复杂，Orchestrator 可请求 `TaskContextAgent` 生成 Subtask 建议列表供用户选择。
