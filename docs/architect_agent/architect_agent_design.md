# 模块设计文档：`architect_agent` (架构师大脑引擎)

## 1. 模块定位
`architect_agent` 是挂载在物理目录 `smart_task_app/agents/architect` 中的具体能力落地模块。它属于 ADK 标准 Agent 实现，专门承担在项目早期与用户交流，拆解目标、设计图纸，并向系统写入执行大纲（Task 蓝图）的顶层大脑角色。

## 2. 系统核心职责
- **业务需求抽象**：与客户或其他外部环境输入对接，了解开发需求，提炼技术难点。
- **项目/资产初始化**：直接调用并联通系统的 `task_management` 层 API。创建具体的 `project`, `activity`, `module`, 到微观的 `tasks` 并组装 `depends_on` 的图执行拓扑逻辑。
- **设计稿落地**：利用 `execute_shell` 抑或系统文件写入能力（视当前工作空间 `SMART_WORKSPACE_PATH` 配置而定），将沟通结果、需求蓝图直接固化为 Markdown 或者 Mermaid 图表，为后续执行者铺路（存放于 `docs/` 下的各个同名子域）。
- **交接与反馈**：当所有模块前置规划梳理完毕，它会自动在主流程中确认自身任务完结向 `mcp_server` 的路由发送结束信号（反馈 `status='code_done'`）。

## 3. 设计原则
- **不触碰业务代码**：它的权限可以进行探索，但严禁向具体的 `src/` 写逻辑代码。
- **高阶抽象要求**：由于被定义为"架构师"身份，Prompt 指令内着重强调了 "Design Pattern, Modularization, Decoupling, Interface-first" 的强制思考流要求。

## 4. 驱动与上下文依赖
- 它的唤醒全凭调度引擎通过 `uv run adk run smart_task_app/agents/architect` 的命令行触发。
- 初始化时必须承接操作系统的 `SMART_TASK_ID` 来溯源环境信息。
