from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.agent_utils import (
    query_context, execute_shell, submit_task_deliverable, report_blocker
)

root_agent = LlmAgent(
    name="execution_trader",
    model=MODEL,
    description="Execution Trader (执行交易员): 负责将策略接入订单流，在 Paper Trading 环境下测试信号分发与滑点控制。",
    instruction="""You are the Execution Trader. 
Your focus is Execution Efficiency & Connectivity.
If a task ID is provided via SMART_TASK_ID, use query_context.
Use execute_shell to test broker APIs or run trading simulators.
Analyze slippage and execution latencies.
Report blockers via report_blocker.
Finally, use submit_task_deliverable to report status ('code_done') and execution metrics.
""",
    tools=[query_context, execute_shell, submit_task_deliverable, report_blocker]
)

app = App(
    name="execution_trader",
    root_agent=root_agent,
    plugins=[]
)
