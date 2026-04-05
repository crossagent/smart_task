# 模块设计文档：`coder_agent` (搬砖迭代引擎)

## 1. 模块定义 (Module Definition)
`coder_agent` 是 Smart Task Hub 的具体实施单元，存放在 `smart_task_app/agents/coder`。它的核心功能是承接架构师设计的子任务，在受控的物理工作区内进行真机代码编写、单元测试及其 Git 提交。

## 2. 模块接口 (Module Interface)
- **输入 (Input)**：
    - 运行时环境变量 `SMART_TASK_ID`。
    - 指向特定物理工作区的 `SMART_WORKSPACE_PATH`。
    - 架构师之前生成的、与该任务相关的子域设计文档（Markdown）。
- **输出 (Output)**：
    - 在 `src/` 目录中真实生成的业务逻辑文件（Python, SQL 等）。
    - 运行全量模块测试后得到的终端回传。
    - 带有任务编号的 Git 提交消息。

## 3. 模块流程 (Module Flow)
1. **现状认知**：读取环境变量，根据任务 ID 从数据库调取当前需要完成的“迭代目标”。
2. **环境探测**：通过 `grep`, `ls` 等工具观察此时工作区的代码现状与架构师给出的 Markdown 规范。
3. **分阶段实施**：先编写代码骨架，并同步编写对应的 `tests/` 下的单元测试用例。
4. **自检循环 (TDD)**：在受控终端发起 `pytest` 指令。如果报错，则原地进行 Debug 与代码重构，直至通过。
5. **版本快照**：调用 `git add/commit` 将工作成果固化在当前分支。
6. **任务完结**：通过 MCP Tooling 将数据库任务状态置为 `code_done`，释放资源。
