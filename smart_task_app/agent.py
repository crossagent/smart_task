from __future__ import annotations

import os
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents import SequentialAgent
from google.adk.apps import App
from google.adk.plugins import LoggingPlugin
from .shared_libraries.constants import MODEL

# 1. 定义远程 Architect Expert (分解专家)
# 默认端口 9011，支持环境变量覆盖
ARCHITECT_URL = os.getenv("ARCHITECT_AGENT_URL", "http://task_planner:9011/a2a/task_planner/.well-known/agent-card.json")
architect_agent = RemoteA2aAgent(
    name="architect",
    agent_card=ARCHITECT_URL,
    description="负责逻辑熵减与载荷驱动的任务分解"
)

# 2. 定义远程 Coder Expert (原子化专家)
# 默认端口 9012，支持环境变量覆盖
CODER_URL = os.getenv("CODER_AGENT_URL", "http://coder_expert:9012/a2a/coder_expert/.well-known/agent-card.json")
coder_agent = RemoteA2aAgent(
    name="coder",
    agent_card=CODER_URL,
    description="负责交付锚点与物理架构的原子化实现"
)

# 3. 使用标准 A2A Sequential 模式构建流水线
# 这是 ADK 最推荐的多 Agent 协作方式：架构师分解 -> 代码实现
root_agent = SequentialAgent(
    name="hub_pm",
    sub_agents=[architect_agent, coder_agent],
    description="Project Manager (项目经理): 负责宏观任务分配与多专家协同调度。"
)

# 4. App 配置
# 这里我们定义主 App，它作为外部访问的唯一入口
app = App(
    name="hub_pm",
    root_agent=root_agent,
    plugins=[LoggingPlugin()]  # 标准 A2A/Agent 日志打印方式
)
