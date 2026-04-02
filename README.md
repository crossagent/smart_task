# Smart Task Hub (STH) - Structured Task Management Server

> 一个面向 LLM 协作而设计的、结构化的任务管理中枢。

## 🌟 设计初衷 (Design Mindset)

在复杂的项目协作中，任务往往在不同维度间跳跃：从用户的原始需求 (Project)，到业务层的执行活动 (Activity)，再到底层代码资产 (Module) 的修改，以及人力资源 (Resource) 的分配。

**Smart Task Hub** 的核心设计思路是**“分层治理与降维计算”**，在结构上天然为 **Multi-Agent System (多智能体系统)** 的协作流程做了最优适配。它将系统拆解为五个核心维度，形成严密的流转网络：

1. **Project (战略项目池 - The Inbox)**: 管理宽泛、非结构化的意图边界，捕获最初的外部需求。
2. **Activity (执行活动 - The Strategy/Path)**: 交付价值的执行路径。拆解真实的业务属性，定义总体预期收益与终局时间线。
3. **Module (物理实体 - The Entity)**: 系统知识图谱中的最小物理节点。建议将其细分为足够颗粒度的组件 (Component Tree)，使得落入其中的变动天然带有“影响边界锁”。
4. **Resource (资源/执行人 - The Bandwidth)**: 执行的主体，决定并发上限与物理时间可用性。
5. **Task (原子粒子 - The Delta Vector)**: 每一个 Task 仅对应一个 Module 与一个 Activity。它是状态变化的原子单位。
    * **语义矢量 (`module_iteration_goal`)**: 采用自然语言陈列要在目标 Module 细粒度上发生的迭代增量与影响。
    * **结构化依赖推导 (`depends_on`)**: 将“排期仲裁权”交给基于自然语言的语义分析。方案分析代理（Architect Agent）通过比对各任务的 `module_iteration_goal`，推演时序逻辑冲突，并将其固化为严格的有向无环图结构，输出至 `depends_on` 字段，完成降维。

---

## 🏗️ 架构概览 (Architecture)

### 1. 数据模型 (Data Model)

本项目采用了 PostgreSQL 作为持久化层，其核心表结构设计遵循以下逻辑：

```mermaid
graph TD
    Project(Project: 战略项目池) -.-> Activity(Activity: 执行活动)
    Activity --> Task(Task: 原子粒子)
    Module(Module: 模块资产) --> Task
    Resource(Resource: 人员/带宽) --> Task
```

*   **唯一 ID 体系**: 采用 `PRE-YYYYMMDD-XXXX` 格式。
*   **双参校验模式**: 接口采用 `xxx_id` + `xxx_id_name` 的双参数模式（例如 `resource_id` 和 `resource_id_name`）。大模型在调用工具时需同时填写，以便人类在审计界面一眼看出 ID 对应的具体内容，确保操作的准确性。
*   **解耦溯源模型**: Task 强映射 Activity，Activity **弱依赖** Project。内部存储完全 ID 化，外部交互通过冗余的名字参数实现人类友好型校验。

### 2. 边界哲学: 结构化算力 vs 非结构化智能 (Structure vs Semantics)

在系统底座的字段设计上，我们坚守一条架构铁律：**“把确定性交给算力，把不确定性交给智能”**（即用结构化的缸，盛放非结构化的水）。

*   **强结构化防呆 (The Structured Bones)**：
    *   代表字段：`parent_module_id` (外键)、`depends_on` (原生 PostgreSQL 数组)。
    *   设计主张：凡是涉及**流程控制 (Control Flow)**、**空间拓扑 (Spatial Topology)** 和**数学排期运算 (Graph Math)** 的节点链接，必须使用最死板的数据库约束锁死。例如排期引擎（Scheduler Engine）必须依赖规整的 `depends_on` 拓扑排序算法运转，而非解析自然语言。
*   **非结构化扩展 (The Semantic Flesh)**：
    *   代表字段：`layer_type` (模块层级刻度, `VARCHAR`)、`module_iteration_goal` (模块增量逻辑, `TEXT`)。
    *   设计主张：凡是涉及**业务意图 (Business Intention)**、**实体规模定性 (Scale Categorization)** 和**执行上下文 (Cognitive Context)** 的节点，必须交由 LLM 动态推演，拒绝通过 `Enum` 锁死演进路径。例如，一个 Module 可以在 AI 视角下从 `L2-Service`（微服务）自然泛化为 `L1-Domain`（国家/公司实体），而无需修改任何底层 Schema。

### 3. 技术栈 (Technology Stack)

*   **FastAPI & FastMCP**: 利用 [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)，使该服务器能够无缝对接 AI 智能体（如 Claude, GPT-4），使其具备读写任务数据的能力。
*   **psycopg3**: 异步驱动确保在高并发下依然能保持响应。
*   **Docker & Docker Compose**: 一键部署，环境隔离。

---

## 🛠️ 核心功能工具 (MCP Tools)

本服务器向 LLM 暴露了多维度的工具集：

| 分类 | 工具示例 | 说明 |
| :--- | :--- | :--- |
| **CRUD** | `create_project`, `update_task`, etc. | 完整的生命周期管理。 |
| **查询驱动** | `execute_query` | 支持只读 SQL，允许 AI 进行跨表统计和复杂逻辑分析。 |
| **元数据发现** | `get_db_schema` | 允许 AI 动态获取表结构，辅助其在没有预设指令的情况下构建查询。 |

---

## 🚀 快速开始

### 1. 环境配置
在根目录下创建 `.env` 文件：
```env
DB_HOST=
DB_PORT=
DB_USER=
DB_PASSWORD=
DB_NAME=
PORT=
```

### 2. 数据库初始化
执行 `init_smart_task.sql` 中的脚本以创建必要的数据库和表。

### 3. 使用 Docker 部署
```bash
docker-compose up -d --build
```

---

## 💡 使用场景示例

1.  **需求捕获（Project）**: 用户非结构化输入“我想在页面加个搜索功能”，由服务栈生成 `upsert_project` 记录。
2.  **业务策略层 (Activity)**: 读取 Project 生成对口 `Activity`，定义业务/执行目标、限定 Owner 与边界。
3.  **结构化降维 (Architect)**: 方案结构拆解 AI 读取 Activity 意图与对口的细粒度 Module，下推生成多个原子级 `Task`。它基于阅读各任务的自然语义 `module_iteration_goal` 锁定潜在冲突边界，生成能够规避执行阻塞的硬性拓扑依赖链 `depends_on`。
4.  **数学排期引擎 (Scheduler Engine / Agent)**: 脱离理解复杂业务的包袱，完全降维为图论状态机。通过读取已经梳理完的无环图 `depends_on` 与资源的并发物理约束，计算出带有强烈确定性的精准时轴 (`start_date`, `due_date`)。

---
