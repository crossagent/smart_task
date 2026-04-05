# 模块设计文档：`coder_agent` (开发流水线引擎)

## 1. 模块定位
`coder_agent` 存放在 `smart_task_app/agents/coder` 中。它是一个 ADK 标准 Agent 实现，也是整个 Smart Task Hub 底层架构中真正“弄脏手去搬砖”的终点执行端点。

## 2. 核心职责
- **阅读环境与文档**：承接被分配到的特定迭代目标 (`module_iteration_goal`)，在工作区中利用 `grep`、`cat`、甚至直接读取 `architect` 写在 `docs/<module>/` 里的 Markdown 来重建当前大脑认知结构。
- **代码实施**：直接动用代码生成能力，创建 `src/` 目录下的业务逻辑，更新依赖、修改表结构、注入路由。
- **执行 TDD 测试**：不仅要写代码，还要自行跑终端命令行拉取 `pytest`。通过对所做出的模块测试来证明代码逻辑的可用性并确保自己没出错。
- **版本控制与自我完结**：一切改动自测无误后，负责执行 `git add/commit`，并通过外部调令更新中央数据库状态为 `code_done`。

## 3. 工具装备配置
它预设被装载以下标准能力簇：
- **`query_context`**: 查阅自己的来龙去脉（我属于什么任务？谁分配我的？）。
- **`execute_shell`**：通过子进程或者直接 `os.system` 与操作系统的终端建立信任联系，发起任意 bash / powershell 指令（基于工作区限制）。

## 4. 并发解耦隔离性
由于 `coder_agent` 往往属于被大规模横向扩展调用的群体（例如通过生成 5 个平行的子进程同时跑 5 个 task），它的核心安全性来自于前置 `architect_agent` 划分出的独立微模块（比如一个 coder 只准动 `mcp_server` 的文件，另一个 coder 只能改 `task_execution` 的文件）。只要顶层图依赖切得清楚，底层多个 `coder` 绝不打架。
