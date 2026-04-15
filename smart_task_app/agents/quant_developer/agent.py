from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.agent_utils import (
    query_context, execute_shell, submit_task_deliverable, report_blocker
)

root_agent = LlmAgent(
    name="quant_developer",
    model=MODEL,
    description="Quant Developer (量化系统工程师): 接手研究员的数学原型，重构成高可用、高并发的实盘级生产代码，加固基础设施。",
    instruction="""You are the Quant Developer in the trading firm. 
Your focus is System Infrastructure & Optimization.
If a task ID is provided via SMART_TASK_ID, use query_context to understand the requirements.
Perform implementation tasks (refactoring, optimization, boilerplate generation) and run tests using execute_shell.
If you run into unresolvable issues, use report_blocker.
Finally, ALWAYS use submit_task_deliverable to report your work status ('code_done') and a summary of your changes.
""",
    tools=[query_context, execute_shell, submit_task_deliverable, report_blocker]
)

app = App(
    name="quant_developer",
    root_agent=root_agent,
    plugins=[]
)
