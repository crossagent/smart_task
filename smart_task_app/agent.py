from __future__ import annotations

import os
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.agents import SequentialAgent
from google.adk.apps import App
from google.adk.plugins import LoggingPlugin
from .shared_libraries.constants import MODEL

# 1. 定义远程 Architect Agent (分解专家)
# 它运行在端口 9011
architect_agent = RemoteA2aAgent(
    name="architect",
    agent_card="http://localhost:9011/.well-known/agent.json",
    description="负责逻辑熵减与载荷驱动的任务分解"
)

# 2. 定义远程 Coder Agent (原子化专家)
# 它运行在端口 9012
coder_agent = RemoteA2aAgent(
    name="coder",
    agent_card="http://localhost:9012/.well-known/agent.json",
    description="负责交付锚点与物理架构的原子化实现"
)

# 3. 使用标准 A2A Sequential 模式构建流水线
# 这是 ADK 最推荐的多 Agent 协作方式：架构师分解 -> 代码实现
root_agent = SequentialAgent(
    name="SmartTaskPipeline",
    agents=[architect_agent, coder_agent],
    description="智能任务分解与执行流水线 (A2A 标准版)"
)

# 4. App 配置
# 这里我们定义主 App，它作为外部访问的唯一入口
app = App(
    name="smart_task_app",
    root_agent=root_agent,
    plugins=[LoggingPlugin()]  # 标准 A2A/Agent 日志打印方式
)
