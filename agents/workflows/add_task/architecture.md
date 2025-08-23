# 添加任务工作流：架构与数据契约 (v2)

本文档定义了 `add_task` 工作流的技术架构，重点关注其核心数据模型以及协调器 (Orchestrator) 和专业代理 (Agent) 之间的数据契约。

## 指导原则

1.  **模型驱动**: 工作流的核心是围绕两个核心数据模型——`Project` 和 `Task`——来构建的。
2.  **直接数据交换**: 每个代理直接返回其核心业务数据，以简化实现。
3.  **协调器即状态机**: `Orchestrator` 负责管理工作流的整体状态，按顺序调用代理，并使用它们的直接输出来决定下一步行动。

## 1. 核心数据模型 (Core Data Models)

这是整个系统的基石。所有信息收集的目标都是为了填充这些模型的字段。

### 1.1. 项目 (Project)
*   **定位**: 一个宏大的、有明确目标的长期计划。
*   **核心字段**:
    *   `id` (string): 项目的唯一标识符，例如 "PROJ-2025-Q4"。
    *   `title` (string): 项目的名称。
    *   `description` (string): 对项目的简要描述。
    *   `goal` (string): 项目的最终目标，说明“为什么要做这个”。
    *   `status` (string): 项目状态 (`规划中`, `进行中`, `已完成`, `已搁置`)。
    *   `owner` (string): 项目负责人。
    *   `due_date` (date): 预期完成日期。
    *   `notion_page_id` (string): 对应的Notion数据库页面ID。

### 1.2. 任务 (Task) - (统一模型)
*   **定位**: 一个可交付的工作单元，**可以是顶级任务，也可以是另一个任务的子任务**。
*   **核心字段**:
    *   `id` (string): 任务的唯一标识符，例如 "TASK-128"。
    *   `title` (string): 任务的标题。
    *   `description` (string): 任务的详细描述。
    *   `parent_project_id` (string): **(顶级任务需要)** 所属项目的 `id`。
    *   `parent_task_id` (string): **(子任务需要)** 所属父任务的 `id`。
    *   `status` (string): 任务状态 (`待处理`, `进行中`, `待审核`, `已完成`)。
    *   `priority` (string): 任务优先级 (`高`, `中`, `低`)。
    *   `assignee` (string): 任务执行人。
    *   `due_date` (date): 截止日期。
    *   `notion_page_id` (string): 对应的Notion数据库页面ID。

---

## 2. 代理职责与直接数据契约

### A. 上下文收集助手 (ContextualSearchAgent)

*   **核心职责**: **连接现在与过去**。通过搜索知识库，为当前对话提供背景信息。
*   **直接输出**:
    ```json
    {
      "related_projects": [{ "id": "PROJ-123", "name": "用户中心重构" }],
      "related_tasks": [{ "id": "TASK-456", "title": "设计登录页面UI" }]
    }
    ```

### B. 任务颗粒度判断助手 (GranularityAdvisorAgent)

*   **核心职责**: **定义问题的规模**。根据用户描述和上下文，判断新事项应为 `PROJECT` 还是 `TASK`。
*   **直接输出**:
    ```json
    {
      "granularity": "TASK" // "PROJECT" 或 "TASK"
    }
    ```

### C. 信息收集助手 (InformationCollectorAgent)

*   **核心职责**: **填满所需信息的“表单”**。根据 `GranularityAdvisorAgent` 的判断，以**核心数据模型**为目标，收集创建 `Project` 或 `Task` 所需的信息。
*   **直接输出**: 输出的 `collected_data` 字段结构 **必须** 与 `Project` 或 `Task` 的核心数据模型一致。
    ```json
    // 示例：当颗粒度为 TASK 时
    {
      "granularity": "TASK",
      "collected_data": {
        "id": null,
        "title": "修复登录页面的一个bug",
        "description": null,
        "parent_project_id": "PROJ-123",
        "parent_task_id": null,
        "status": "待处理",
        "priority": null,
        "assignee": null,
        "due_date": null,
        "notion_page_id": null
      }
    }
    ```

### D. 结果判断助手 (CompletionValidatorAgent)

*   **核心职责**: **担当守门员**。在信息收集后，对照核心数据模型的必填字段，判断信息是否完整。
*   **直接输出**: 通过 `is_complete` 字段来区分不同场景。
*   **场景1: 信息不完整**
    ```json
    {
      "is_complete": false,
      "missing_fields": ["description", "assignee"],
      "clarification_question": "好的，这个任务将属于‘用户中心重构’项目。您能更详细地描述一下这个bug吗？应该指派给谁？"
    }
    ```
*   **场景2: 信息完整，准备确认**
    ```json
    {
      "is_complete": true,
      "confirmation_prompt": "好的。我准备创建以下任务：\n- **标题**: 修复登录页面的一个bug\n- **所属项目**: 用户中心重构\n\n是否继续？"
    }
    ```
