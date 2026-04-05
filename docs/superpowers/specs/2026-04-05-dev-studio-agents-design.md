# Smart Task Hub — Dev Studio Agent 架构设计

**日期**: 2026-04-05  
**状态**: 待实现  
**范围**: 为 STH 引入可执行的 Remote Agent 执行层，聚焦软件开发场景

---

## 1. 背景与目标

STH 当前已有完善的任务管理中枢：五层数据模型（Project → Activity → Task + Module + Resource）、MCP Server、PostgreSQL 持久化。但缺少真正能"干活"的执行单元——任务被拆解和排期后，仍需人工手动执行。

**目标**：引入基于 ADK remote agent 的执行层，让 Task 在 `depends_on` DAG 驱动下自动流转并被 agent 执行。人工的角色收缩为 Activity 粒度的路径审核，以及关键节点的 checkpoint。

**不做什么**：
- 不实现 Dispatcher 自动选择 agent（当前人工分配 resource）
- 不引入 CI/CD 集成（agent 只负责到 push，不负责部署）
- 不实现 Reviewer Agent（review 作为 Coder 自身的 checklist）

---

## 2. 核心设计原则

**Resource = Remote Agent**：STH 的 `resource` 表不只是"人"，也是 agent 实例的注册表。每个 remote agent 在 `resource` 表中有一条记录，包含其 endpoint 和能力类型。未来扩展新能力只需注册新的 resource 条目，框架不变。

**Task 状态机是协调中枢**：agent 之间不直接通信，通过 task 状态的流转做隐式协调。STH 是唯一的事实来源。

**三层溯源**：Coder agent 拿到 task 后，可沿 `task → activity → project` 溯源完整的业务意图，不只是执行原子指令。

---

## 3. Agent 清单

### 3.1 Architect Agent

| 项 | 内容 |
|---|---|
| **触发方式** | 人工手动（Activity 创建时，或 Module 结构需要变动时） |
| **Resource 类型** | `architect` |
| **输入** | Activity ID |
| **输出** | 创建/更新 Tasks（含 `module_iteration_goal` 和 `depends_on` DAG）；必要时更新 Module 树 |

**职责边界**：
- 读取 Activity 意图，溯源 Project 背景
- 识别涉及的 Module，评估是否需要裂变（基于"载荷视角"）
- 拆解原子 Task，每个 task 满足「单人·单模块·单目标」原则
- 比对各 task 的 `module_iteration_goal`，推演时序逻辑冲突，写入 `depends_on` 字段

**工具**：
- STH MCP 全套工具（create/update project、activity、module、task）
- 代码仓库只读访问（了解现有 Module 的实际代码结构）

**不做什么**：不写代码，不操作 git，不执行测试。

---

### 3.2 Coder Agent（N 个并发实例）

| 项 | 内容 |
|---|---|
| **触发方式** | Scheduler dispatch（task 状态变为 `ready`，且 `resource_id` 指向该 agent） |
| **Resource 类型** | `coder` |
| **实例数量** | 每个实例有独立的工作目录和 git clone |
| **输入** | Task ID |
| **输出** | Feature branch + commit，task 状态更新为 `code_done` |

**职责边界**：
- 三层溯源：task → activity → project，获取完整上下文
- 在独立 git worktree/clone 中 checkout feature branch
- 实现 `module_iteration_goal` 描述的状态变更
- 编写测试用例（当 task 目标是测试资产时，本 agent 同样处理）
- 跑现有 pytest，确保不破坏已有用例
- commit/push，更新 task 状态

**工具**：
- STH MCP 工具（读 task/activity/project/module，更新 task 状态）
- 本地 git 操作（checkout、commit、push）
- 文件系统读写（代码修改）
- pytest 执行

**并发隔离**：每个 Coder 实例通过各自的 git clone 目录或 git worktree 隔离工作区，互不干扰。Task 的 `resource_id` 确保同一 task 不会被两个 Coder 同时领取。

---

### 3.3 Scheduler

| 项 | 内容 |
|---|---|
| **类型** | 内置轻量级服务（不是 LLM agent） |
| **触发** | Task 状态变更事件 |
| **职责** | 纯图遍历，零业务逻辑 |

**逻辑**：
```
当 task.status → done:
  查询所有 depends_on 包含此 task_id 的下游 task
  对每个下游 task:
    检查其所有前置 task 是否全部 done
    若是: 将该 task 状态改为 ready
          调用 task.resource.endpoint（Remote Agent）
```

**人工介入点**：人工在 Activity 粒度审核整条 task 路径后"放行"，Scheduler 才开始对该 Activity 下的 task 进行自动推进。人工可随时暂停某条路径。

---

## 4. Resource 表扩展

当前 `resource` 表需要新增字段以支持 agent 注册：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `resource_type` | VARCHAR | `human` / `architect` / `coder` / 未来扩展 |
| `agent_endpoint` | VARCHAR | Remote Agent 的 A2A endpoint URL，human 类型为空 |
| `workspace_path` | VARCHAR | agent 本地 git clone 目录，human 类型为空 |
| `is_available` | BOOLEAN | 当前是否可接受新 task dispatch |

---

## 5. Task 状态机

```
pending → ready → in_progress → code_done → done
                                           ↘ blocked（人工标记）
```

| 状态 | 含义 | 触发者 |
|---|---|---|
| `pending` | 等待前置任务 | 初始创建 |
| `ready` | 前置全部完成，可执行 | Scheduler |
| `in_progress` | Agent 已领取，执行中 | Agent |
| `code_done` | 代码已提交，等待人工确认 | Agent |
| `done` | 人工确认完成，Scheduler 可推进 | 人工 |
| `blocked` | 人工标记暂停 | 人工 |

---

## 6. 数据流示例

```
人工: 创建 Activity "支持搜索功能"
        ↓
Architect Agent: 拆解出 3 个 Task，生成 depends_on DAG
        ↓
人工: 审核路径，确认放行
        ↓
Scheduler: Task-1 无前置 → 状态改为 ready → dispatch Coder-01
        ↓
Coder-01: 溯源上下文 → checkout → 实现 → 跑 pytest → push
          → 更新 Task-1 状态为 code_done
        ↓
人工: 确认 Task-1 → 状态改为 done
        ↓
Scheduler: Task-2 前置 Task-1 已 done → ready → dispatch Coder-02
        ↓
...（后续节点自动流转）
```

---

## 7. 扩展路径

未来通过在 `resource` 表注册新的 agent 即可扩展能力，无需修改框架：

| 未来 Agent | `resource_type` | 职责 |
|---|---|---|
| Reviewer Agent | `reviewer` | 自动 code review，输出审查意见 |
| Deploy Agent | `deployer` | 触发 CI/CD 或直接部署 |
| Doc Agent | `doc_writer` | 更新文档和 changelog |
