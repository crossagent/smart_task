from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin
from smart_task_app.shared_libraries.agent_utils import execute_shell

STH_MCP_URL = "http://smart_task_copilot:45666/mcp/"

def fetch_market_data(ticker: str, start_date: str, end_date: str) -> str:
    """Fetches market data for a given ticker and date range using yfinance (mock)."""
    return f"Simulated: Fetched OHLCV data for {ticker} from {start_date} to {end_date}."

root_agent = LlmAgent(
    name="data_engineer",
    model=MODEL,
    description="Data Engineer (数据与特征工程师): 专注于数据的拉取、清洗与特征工程算子开发。",
    instruction=f"""You are the Data Engineer. 
Your focus is Raw Data Management & Feature Pipeline.
If a task ID is provided via SMART_TASK_ID, use the 'get_task_context' tool (from MCP).
You can use fetch_market_data and execute_shell to run pandas/yfinance scripts.
Report blockers via 'report_blocker' (from MCP).
Finally, use 'submit_task_deliverable' (from MCP) to report status ('code_done') and results.

{GLOBAL_LANGUAGE_INSTRUCTION}

Database tools are provided via MCP at {STH_MCP_URL}.
""",
    tools=[
        execute_shell,
        fetch_market_data,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=STH_MCP_URL)
        )
    ]
)

app = App(
    name="data_engineer",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3)]
)
