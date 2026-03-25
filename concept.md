# 添加任务工作流：架构与数据契约 (v2)

本文档定义了 `add_task` 工作流的技术架构，重点关注其核心数据模型以及协调器 (Orchestrator) 和专业代理 (Agent) 之间的数据契约。

## 指导原则

1.  **模型驱动**: 工作流的核心是围绕两个核心数据模型——`Project` 和 `Task`——来构建的。
2.  **直接数据交换**: 每个代理直接返回其核心业务数据，以简化实现。
3.  **协调器即状态机**: `Orchestrator` 负责管理工作流的整体状态，按顺序调用代理，并使用它们的直接输出来决定下一步行动。

## 1. 核心数据模型 (Core Data Models)

这是整个系统的基石。所有信息收集的目标都是为了填充这些模型的字段。定义的关键在于 **“以人为本的交付视角”**。

### 1.1. 项目 (Project) - "Goals & Context"
*   **定位**: **目标 (Goal)**。一个宏大的、有明确目标的长期计划。
*   **核心逻辑**: **"为什么做?"** (Context)
*   **判定标准**: 
    1.  **多交付物**: 包含多个独立的交付物 (Tasks)。
    2.  **长期跟进**: 如果你关注的是整体进度的百分比，而不是某个具体的人，它是 Project。
*   **核心字段**:
    *   `id` (string): 项目的唯一标识符，例如 "PROJ-2025-Q4"。
    *   `title` (string): 项目的名称。
    *   `goal` (string): 项目的最终目标，说明“为什么要做这个”。
    *   `owner` (string): 项目负责人 (负责协调，不一定负责具体代码)。
    *   `status` (string): 项目状态 (`规划中`, `进行中`, `已完成`...)。
    *   `due_date` (date): 预期整体完成里程碑。

### 1.2. 任务 (Task) - "Deliverables & Assignees"
*   **定位**: **交付物 (Deliverable)**。最核心的原子跟进单元。
*   **核心逻辑**: **"谁来交付?"** (Responsibility)
*   **判定标准**:
    1.  **单人负责**: 必须要有一个明确的 Assignee 对结果完全负责。
    2.  **独立交付**: 哪怕依赖他人 (Blocked by)，最终的交付责任依然在 Assignee 身上。
    3.  **协作节点**: Task 之间通过依赖关系 (Dependency) 进行协作，而不是将协作的任务升级为 Project。
*   **核心字段**:
    *   `id` (string): 任务的唯一标识符。
    *   `title` (string): 任务的标题（动词开头，例如“完成API接口”）。
    *   `parent_project_id` (string): 所属项目的 `id`。
    *   `assignee` (string): **核心字段**，任务的唯一直接负责人。
    *   `status` (string): 任务状态 (`To Do`, `In Progress`, `Blocked`, `Done`...)。
    *   `dependency_task_ids` (list): 依赖的前置任务 ID 用来处理协作。
    *   `due_date` (date): 截止日期。

### 1.3. 子任务 (Subtask) - "Action Items & Log"
*   **定位**: **执行步骤/过程 (Action Items)**。
*   **核心逻辑**: **"怎么做/遇到了什么?"** (Execution)
*   **判定标准**:
    1.  **动态生成**: 通常是在执行过程中产生（如“遇到权限问题需申请”、“增加测试步骤”）。
    2.  **个人 checklist**: 属于 Task Assignee 的个人备忘，外部通常只关注 Task 结果，不微观管理 Subtask。
*   **核心字段**:
    *   `id` (string): 子任务ID。
    *   `parent_task_id` (string): 所属父任务的 `id`。
    *   `title` (string): 具体动作。
    *   `is_completed` (boolean): 是否完成。

---

