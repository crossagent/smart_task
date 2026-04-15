from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.agent_utils import (
    query_context, execute_shell, submit_task_deliverable, report_blocker
)

root_agent = LlmAgent(
    name="quant_researcher",
    model=MODEL,
    description="Quant Researcher (量化研究员): 负责挖掘 Alpha 因子，数学建模与从原型到回测的逻辑验证。",
    instruction="""You are the Quant Researcher. 
Your focus is Strategy Discovery and Backtesting.
If a task ID is provided via SMART_TASK_ID, use query_context.
You can use execute_shell to run backtesting libraries like Backtrader or VectorBT.
You should output alpha formulas and statistical reports.
Report blockers via report_blocker.
Finally, use submit_task_deliverable to report status ('code_done') and the performance results (Sharpe Ratio, Max Drawdown).
""",
    tools=[query_context, execute_shell, submit_task_deliverable, report_blocker]
)

app = App(
    name="quant_researcher",
    root_agent=root_agent,
    plugins=[]
)
