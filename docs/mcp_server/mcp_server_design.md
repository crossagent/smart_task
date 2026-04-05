# 模块设计文档：`mcp_server` (服务总线层)

## 1. 模块定位
`mcp_server` 模块是系统物理运行的起点，也是与外部集成（比如 Cursor、Claude Code 等 AI Coding Assistants，或者前端网关）的直接交互界面。在 DDD 设计中，本模块被彻底剥离了具体的业务逻辑，属于“纯防腐层/基础设施层”。

## 2. 核心职责
- **FastMCP 实例装载**：初始化 FastMCP 应用框架，并加载其名称、元数据。
- **Tools 路由装配**：收集并注册其他内聚业务模块（如 `task_management` 模块暴露出来的操作工具），暴露给外部客户端。
- **后台守护进程引导**：在服务器启动时，并发无阻塞地拉起诸如 `scheduler_daemon`（调度轮询引擎）的后台任务，维护程序生命周期。
- **传输协议兼容**：支持通过 `stdio` (IDE 直连) 以及 `http(sse)` (远程服务端访问) 启动。

## 3. 设计原则
- **极简与克制**：本目录下严禁存放任何针对数据库的实质性 SQL 执行动作；严禁存放对 DAG 算法的分支运算。
- **高耦合低入侵**：此模块依赖下层服务（如 `task_management` 暴露的 `register_tools`），但本身不向其他层暴露内部变量。

## 4. 相关依赖
- **外部**：依赖 `mcp` (`FastMCP` 框架包)。
- **内部**：依赖 `src.task_management.tools` (获取业务端点) 和 `src.task_execution.scheduler` (拉起守护器)。

## 5. 可扩展性设计
未来若要添加如 MCP 身份校验、限流器 (Rate Limit) 或自定义日志记录 (Telemetry)，将全部统一挂载在 `server.py` 这个唯一入口中处理，不会影响底层的任务定义流。
