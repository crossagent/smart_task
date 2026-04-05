# 模块设计文档：`task_management` (任务定义与管理层)

## 1. 模块定位
`task_management` 模块处理并维护整个系统的核心领域模型。在这个由任务图组成的智能执行中心里，它充当了系统所有实体的**状态存放点**与**结构查询者**。该领域彻底掌控了与 PostgreSQL 数据库交互的全部权利。

## 2. 核心实体 (Domain Entities)
- **Projects (项目)**：宏观管理维度。
- **Activities (交付产出)**：由架构师规划出的宏观阶段模块集合。
- **Modules (迭代目标)**：代码的聚集单元。
- **Tasks (微任务/节点)**：最小执行单位，包含着其依赖项（`depends_on`），构成了 DAG（有向无环图）。
- **Resources (执行资源)**：槽位概念。决定了谁能接手特定任务（分为 `human`, `architect`, `coder` 等角色，以及物理挂载目录 `agent_dir`）。

## 3. 核心职责
### A. 数据抽象与读写 (`db.py`)
- 提供底层 `execute_query` 和 `execute_mutation` 的纯净封装适配（使用 psycopg2）。
- 集中转换包含日期的混合 JSON 格式(`CustomEncoder`) 以供前端兼容。
### B. AI 交互触角封装 (`tools.py`)
- 定义由大模型调用的 `upsert_*` 和 `delete_record` 系列方法。
- 对表级别的记录管理设置软隔离拦截。
- `get_task_context` 提供了大模型进行宏观到微观上下文穿插必须的上下文追溯链路。

## 4. 并发与冲突防控
所有的 `upsert` 方法全量采用了原生的 `INSERT ... ON CONFLICT DO UPDATE`（即 Upsert 原子操作）。这意味着即使当多个终端、多个 Coder Agent 同时要求创建或修改同一特定标识的信息时，数据库内部原子锁保证了执行数据的绝对一致和防抖，无需在上层业务添加 Python 异步死锁。
