from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin
from smart_task_app.shared_libraries.agent_utils import execute_shell

# Global MCP中枢地址 (Docker内部网桥地址)
STH_MCP_URL = "http://smart_task_copilot:45666/mcp"

root_agent = LlmAgent(
    name="quant_developer",
    model=MODEL,
    description="Quant Developer (量化系统工程师): 接手研究员的数学原型，重构成高可用、高并发的实盘级生产代码，加固基础设施。",
    instruction=f"""You are the Quant Developer. 
Your focus is System Infrastructure & Optimization.
If a task ID is provided via SMART_TASK_ID, use the 'get_task_context' tool (from MCP) to understand the requirements.
Perform implementation tasks and run tests using 'execute_shell'.
If you run into unresolvable issues, use 'report_blocker' (from MCP).
Finally, ALWAYS use 'submit_task_deliverable' (from MCP) to report your work status ('code_done') and summary.

Note: Database tools are provided via the centralized MCP server at {STH_MCP_URL}.
""",
    tools=[
        execute_shell,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=STH_MCP_URL)
        )
    ]
)

app = App(
    name="quant_developer",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3)]
)
