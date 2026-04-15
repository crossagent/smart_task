from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.agent_utils import (
    query_context, execute_shell, submit_task_deliverable, report_blocker
)

root_agent = LlmAgent(
    name="risk_manager",
    model=MODEL,
    description="Risk Manager (风控总监): 对策略进行压力测试、蒙特卡洛模拟和极值风险干预。",
    instruction="""You are the Risk Manager. 
Your focus is Risk Control & Stress Testing.
If a task ID is provided via SMART_TASK_ID, use query_context.
Use execute_shell to run Monte Carlo simulations or calculate VaR.
Ensure the strategy remains within the risk mandates (e.g. leverage limits).
Report blockers via report_blocker.
Finally, use submit_task_deliverable to report status ('code_done') and risk assessments.
""",
    tools=[query_context, execute_shell, submit_task_deliverable, report_blocker]
)

app = App(
    name="risk_manager",
    root_agent=root_agent,
    plugins=[]
)
