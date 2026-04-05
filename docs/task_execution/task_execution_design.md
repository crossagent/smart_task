# 模块设计文档：`task_execution` (任务引擎调度层)

## 1. 模块定义 (Module Definition)
`task_execution` 是系统的自驱动核心（主动推演者）。它的主要功能是分析处于 `pending` 状态的静态任务，通过有向无环图 (DAG) 算法确定哪些任务可以进入执行阶段，并在有空闲物理资源的情况下，通过物理子进程启动对应的 Agent 进行工作。

## 2. 模块接口 (Module Interface)
- **输入 (Input)**：
    - 直接读取数据库中的任务池（Tasks table）。
    - 资源槽位的可用状态（Resources table 中的 `is_available`）。
- **输出 (Output)**：
    - 外部命令行指令（物理启动 `uv run adk run ...`）。
    - 反向回填到数据库的任务状态（`in_progress`, `code_done`, `failed`）。
    - 资源槽位的状态翻转（锁定与释放信号）。

## 3. 模块流程 (Module Flow)
1. **激活判定 (Tick 1)**：轮询所有 `pending` 任务，检查其 `depends_on` 的任务 ID 是否全部在数据库中标记为 `done`。
2. **状态晋升**：满足依赖后，将任务升为 `ready`。
3. **资源匹配 (Tick 2)**：查找所有 `ready` 任务对应的执行资源 ID，并确认资源处于空闲状态。
4. **锁点建立**：瞬间并行锁定资源（`is_available = False`）并标记任务开始（`in_progress`）。
5. **子进程下发**：携带任务 ID 与工作物理路径等环境变量，启动 Agent 子进程。
6. **异步结果收集**：等待进程结束。
7. **闭环状态回写**：根据进程退出码（0 或 非0），自动刷新数据库字段，标志任务最终成败并释放资源。
