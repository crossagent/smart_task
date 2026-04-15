from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin
from smart_task_app.shared_libraries.agent_utils import execute_shell

STH_MCP_URL = "http://smart_task_copilot:45666/mcp"

root_agent = LlmAgent(
    name="quant_researcher",
    model=MODEL,
    description="Quant Researcher (量化研究员): 负责挖掘 Alpha 因子，数学建模与从原型到回测的逻辑验证。",
    instruction=f"""You are the Quant Researcher. 
Your focus is Strategy Discovery and Backtesting.
If a task ID is provided via SMART_TASK_ID, use 'get_task_context' (from MCP).
You can use execute_shell to run backtesting libraries.
Report blockers via 'report_blocker' (from MCP).
Finally, use 'submit_task_deliverable' (from MCP) to report status ('code_done') and performance results.

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
    name="quant_researcher",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3)]
)
