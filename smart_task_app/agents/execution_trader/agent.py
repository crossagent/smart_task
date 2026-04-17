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
    name="execution_trader",
    model=MODEL,
    description="Execution Trader (执行交易员): 负责将策略接入订单流，在 Paper Trading 环境下测试信号分发与滑点控制。",
    instruction=f"""You are the Execution Trader. 
Your focus is Execution Efficiency & Connectivity.
If a task ID is provided via SMART_TASK_ID, use 'get_task_context' (from MCP).
Use execute_shell to test broker APIs or run trading simulators.
Report blockers via 'report_blocker' (from MCP).
Finally, use 'submit_task_deliverable' (from MCP) to report status ('code_done') and execution metrics.

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
    name="execution_trader",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3), GitSyncPlugin()]
)
