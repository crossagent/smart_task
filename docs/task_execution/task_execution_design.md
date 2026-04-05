# 模块设计文档：`task_execution` (任务引擎调度层)

## 1. 模块定位
`task_execution` 脱胎于原有的全能大单体，被明确独立设计为系统的“流程齿轮”和“起搏心脏”。当 `task_management` （任务管理模块）仅仅负责静态记载状态变化时，`task_execution` 负责根据这些静态规则和前后置依赖状态，“主动地”派发指令或切换机器。

## 2. 核心架构逻辑
本模块的核心是唯一的独立守护协程 / 死循环后台任务 `scheduler.py`。
它的底层推进算法严格按照以下二步 Tick 前进：

### Tick 1: DAG 节点激活判定
1. 提取所有处于 `pending` (尚未激活) 的任务节点。
2. 图解判断：如果当前任务没有上游依赖（空 `depends_on`），或者所有 `depends_on` 指针指向的任务在 `task_management` 中的状态均变为 `done`。
3. 执行状态跳跃：将该任务节点晋升为 `ready` 状态。

### Tick 2: 资源匹配与异步下派
1. 提取所有进入 `ready` 状态的任务节点，联合查询它对应的插槽（Resource）。
2. 判断 `is_available`。如果空闲，立即进入锁定流程：
   - 资源设为不可用 (`is_available = False`)
   - 任务设为进行中 (`status = 'in_progress'`)
3. 动态触发并传递下文：调度器获取并提取所关联的 `agent_dir`（如果是一个 AI 系统资源槽）。
4. 通过建立 `subprocess` 开辟一个与主网络服务器平铺的新宿主线程，传递上下文环境变量（例如 `SMART_TASK_ID` 和物理文件工作区 `SMART_WORKSPACE_PATH`）。
5. 子进程自行调用对应 Agent。

## 3. 设计考量 (无代码干预)
- Scheduler **不再负责修改代码**，也不负责**分析逻辑**。它的逻辑仅限于“如果是状态 A 且条件满足，变成状态 B，随后通知打工人出发”。
- 此类设计的核心目的是实现对 Agent 框架（如 ADK）甚至任何其他语言（如 node.js CLI worker）的黑盒容忍度。对于调度器来说，底层只是一条 `uv run adk run <agent_dir>` 外部命令。
