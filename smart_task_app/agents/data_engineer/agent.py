from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.agent_utils import (
    query_context, execute_shell, submit_task_deliverable, report_blocker
)

# Placeholder specialized tool for demonstration
def fetch_market_data(ticker: str, start_date: str, end_date: str) -> str:
    """Fetches market data for a given ticker and date range using yfinance (mock)."""
    return f"Simulated: Fetched OHLCV data for {ticker} from {start_date} to {end_date}."

root_agent = LlmAgent(
    name="data_engineer",
    model=MODEL,
    description="Data Engineer (数据与特征工程师): 专注于数据的拉取、清洗与特征工程算子开发。",
    instruction="""You are the Data Engineer. 
Your focus is Raw Data Management & Feature Pipeline.
If a task ID is provided via SMART_TASK_ID, use query_context.
You can use fetch_market_data (currently a placeholder) and execute_shell to run pandas/yfinance scripts.
Report blockers via report_blocker.
Finally, use submit_task_deliverable to report status ('code_done') and results.
""",
    tools=[query_context, execute_shell, submit_task_deliverable, report_blocker, fetch_market_data]
)

app = App(
    name="data_engineer",
    root_agent=root_agent,
    plugins=[]
)
