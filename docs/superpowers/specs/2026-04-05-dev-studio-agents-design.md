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

**Resource = Agent 槽位（工厂模板）**：STH 的 `resource` 表存储的不是常驻服务的 endpoint，而是创建 agent 所需的**模板定义**——用什么 prompt、挂载哪些 tools、工作空间在哪里。Agent 进程是按需动态创建、执行完即销毁的，工作空间（git clone 目录）是预先置备好的持久资产。有多少个预置工作空间，就能并发多少个同类 agent。

**Task 状态机是协调中枢**：agent 之间不直接通信，通过 task 状态的流转做隐式协调。STH 是唯一的事实来源。

**三层溯源**：Coder agent 拿到 task 后，可沿 `task → activity → project` 溯源完整的业务意图，不只是执行原子指令。

**上下文注入而非硬编码**：agent 的 prompt 是固定模板，task_id 作为运行时上下文注入。同一套模板可被不同 task 复用，agent 行为由注入的上下文决定。

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
| **职责** | 纯图遍历 + agent 实例化，零业务逻辑 |

**逻辑**：
```
当 task.status → done:
  查询所有 depends_on 包含此 task_id 的下游 task
  对每个下游 task:
    检查其所有前置 task 是否全部 done
    若是:
      将该 task 状态改为 ready
      读取 task.resource → 获取模板定义
      动态创建 agent 实例，注入 task_id 上下文
      在 resource.workspace_path 下执行
      执行完毕后销毁进程，释放 is_available
```

**人工介入点**：人工在 Activity 粒度审核整条 task 路径后"放行"，Scheduler 才开始对该 Activity 下的 task 进行自动推进。人工可随时将任意 task 标记为 `blocked` 暂停路径。

---

## 4. Resource 表扩展

Resource 表从"人员登记册"扩展为"agent 槽位注册表"。每条记录描述一个可被 Scheduler 实例化的能力槽位：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `resource_type` | VARCHAR | `human` / `architect` / `coder` / 未来扩展 |
| `prompt_template` | VARCHAR | prompt 模板文件路径，human 类型为空 |
| `tools_config` | JSONB | 该槽位挂载的 tools 列表，human 类型为空 |
| `workspace_path` | VARCHAR | 预置的 git clone 目录，human 类型为空 |
| `is_available` | BOOLEAN | 当前工作空间是否空闲，可接受新 task |

**实例化流程**：

```
Scheduler 触发 dispatch:
  1. 读取 task.resource_id → 拿到 Resource 记录
  2. 读取 prompt_template + tools_config
  3. 将 task_id 注入 prompt 上下文
  4. 动态创建 LlmAgent(prompt=rendered_template, tools=tools_config)
  5. 在 workspace_path 下运行 agent
  6. agent 执行完毕 → 进程销毁
  7. 更新 resource.is_available = true
```

扩展新能力只需在 `resource` 表新增一条记录（指向新的 prompt 模板和 workspace），无需修改 Scheduler 逻辑。

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
