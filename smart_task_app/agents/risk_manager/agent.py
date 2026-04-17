from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL, GLOBAL_LANGUAGE_INSTRUCTION
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin, GitSyncPlugin
from smart_task_app.shared_libraries.agent_utils import execute_shell

STH_MCP_URL = "http://smart_task_copilot:45666/mcp/"

root_agent = LlmAgent(
    name="risk_manager",
    model=MODEL,
    description="Risk Manager (风控总监): 对策略进行压力测试、蒙特卡洛模拟和极值风险干预。",
    instruction=f"""You are the Risk Manager. 
Your focus is Risk Control & Stress Testing.
If a task ID is provided via SMART_TASK_ID, use 'get_task_context' (from MCP).
Use execute_shell to run Monte Carlo simulations or calculate VaR.
Report blockers via 'report_blocker' (from MCP).
Finally, use 'submit_task_deliverable' (from MCP) to report status ('code_done') and risk assessments.

{GLOBAL_LANGUAGE_INSTRUCTION}

Database tools are provided via MCP at {STH_MCP_URL}.
""",
    tools=[
        execute_shell,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=STH_MCP_URL)
        )
    ]
)

app = App(
    name="risk_manager",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3), GitSyncPlugin()]
)
