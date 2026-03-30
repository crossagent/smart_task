# 🚀 Smart Task Agent (Logseq DB Version)

> [!IMPORTANT]
> **2026 重构版：全平移至 Logseq DB 架构。** 
> 弃用了云端 Notion，转向基于本地图数据库（Local Graph DB）的自动化治理。
> 这是一个以 **原子化（Atomization）** 为核心，由 AI Agent 强力驱动的状态机引擎。

## 🧭 设计哲学：底层实体化，顶层视图化

这套系统致力于解决传统协同工具的“填报滞后”问题。我们通过将工作分解为物理实体的状态变更（Flow），让 AI 能够通过观测图数据库的拓扑结构，自动还原真实的执行进展。

### ⚙️ 原子化与自动化治理

**原子化（Atomization）** 是实现自动化治理的唯一前提。当工作被拆解为 `Flow` 并锚定在特定的 `Module`、`Resource` 和 `Information` 上时，AI 就不再是简单的文本生成器，而是一个**状态机计算引擎**：

1.  **自动排期 (Automated Scheduling)**：基于 Flow 的带宽需求、Module 的物理约束及 Feature 的逻辑依赖，AI 通过拓扑排序自动推演最佳路径。
2.  **自动更新状态 (Automated State Updates)**：Flow 代表了 Module 状态的明确变迁。只要关联的代码被 Check 或 Blocked，状态便客观生成，无需人工填报进度。
3.  **自动汇报 (Automated Reporting)**：AI 沿着 Graph 向上聚合，通过单一批原子数据为 PM、技术、负责人提供完全不同的视图切面。

---

## 🏛 核心五大实体 (5-Entity)

### 🌊 Flow (Task) — 「此刻实际在发生什么」
Task 是最小可执行原子，也是 **Flow** 的具体表现形式。它是系统中最底层的状态迭代路径。
*   **物理归属**：必须绑定一个 `Module`。
*   **动能归属**：必须绑定一个 `Resource`。
*   **协同关系**：通过 `feature:: ((uuid))` 关联逻辑目标。

### 📦 Module (物理域) — 「这件事属于哪个知识域」
Module 是沉淀状态与资产的静态容器。它有明确的负责人，是所有 Flow 最终作用并发⽣改变的靶点。关联对应的知识库（Knowledge Base），让 AI 拥有架构决策的长期记忆。

### 👤 Resource (带宽池) — 「谁来做，能做多少」
Resource 不是静态名单，而是系统的动能来源。它定义了执行带宽的上限和技能边界。

### ✨ Feature (协同容器) — 「跨模块的协作目标是什么」
Feature 是 **Flow + Module + Resource + Information** 的结构化集合。它是协作的最小闭环单元，完成后知识将沉回各个相关的 Module。

### 📥 Initiative (宏观诉求) — 「源头是什么，诉求是否被满足」
Initiative 承担双重职能：作为 Inbox 记录原始诉求，作为顶层视图聚合所有关联的 Feature 与 Task。

---

## 🛠 技术架构

*   **存储引擎**：[Logseq (DB Version)](https://logseq.com/) - 本地 SQLite 图数据库。
*   **通信协议**：[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) - 通过 `mcp-logseq` 实现 Agent 与 Graph 的深层交互。
*   **AI 引擎**：Google Gemini 2.0 / 3.0 系列。
*   **编排框架**：ADK (Agent Development Kit)。

---

## 🚀 快速开始

### 1. 环境准备
*   安装 **Logseq (DB 版本)** 并创建一个图形库。
*   开启 **Settings > API**，生成一个 **API Token**。
*   确保本地已安装 `uv` 包管理器。

### 2. 配置环境
在根目录下创建 `.env` 文件：
```bash
GOOGLE_API_KEY=your_gemini_key
LOGSEQ_API_TOKEN=your_token_generated_above
LOGSEQ_API_URL=http://localhost:12315
LOGSEQ_GRAPH_NAME=your_graph_name
```

### 3. 运行 Agent
```bash
# 启动 Web UI 交互界面
adk web smart_task_app

# 或者直接运行特定 Agent
adk run smart_task_app/task_decomposition
```

---

## 🔗 体系联动

**同一批 Task (Flow)，被四种视角同时观察。这就是底层实体化、顶层视图化的真实含义。**
1.  **Resource 视角**：查看当前分配给我的带宽利用率。
2.  **Module 视角**：查看某个技术模块的健康度与待办。
3.  **Feature 视角**：追踪跨模块功能的交付闭环。
4.  **Initiative 视角**：全局战略诉求的满足程度。
