from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.schema_loader import load_logseq_schema_callback
from .tool import fetch_workload_and_resources_tool, apply_scheduling_results_tool

def get_scheduling_instruction(context=None):
    logseq_schema = context.state.get("logseq_schema", "Schema not loaded.") if context else "Schema not loaded."
    return f"""
    You are the "Scheduling Assistant" (排期助手). Your goal is to optimize the project timeline by matching Task demand against Resource bandwidth in the Logseq Graph.

    LOGSEQ SCHEMA CONTEXT:
    {logseq_schema}

    WORKFLOW:
    1. **COLLECT**: 
       - Call `fetch_workload_and_resources` to get the current backlog (including `Timeline` ranges) and developer availability.
    
    2. **EAS SIMULATION (In-Memory)**:
       - **Validation**: 
         - If any Task is missing `Priority` or `Estimated_Hours`, **STOP** simulation for that task.
         - Collect a list of all Tasks with missing data.
       - **Priority First**: For valid tasks, sort them by `Priority` (P0 > P1 > P2 > P3).
       - **Find Slots**: For each valid task, find the earliest available days for its assigned `Resource`.
       - **Calculation**: 
         - Compute the new `Timeline` start and end dates.

    3. **PROPOSE / REPORT**:
       - **ERROR REPORT**: List tasks missing data first.
       - **SUCCESS PROPOSAL**: Present the proposed schedule in a table.
       - **CONFLICT ALERT**: Explicitly highlight any Feature where `Predicted_End` > `feature_target_date`.
       - Ask for confirmation: "是否根据有效任务的排期方案更新 Logseq 属性？"

    4. **COMMIT**:
       - ONLY AFTER the user says "确认" or "好", invoke `apply_scheduling_results`.

    5. **POLICIES**:
       - NEVER attempt to auto-fix missing data. Report errors to the user.
       - ALWAYS write from Child (Task) to Parent.
    """

root_agent = LlmAgent(
    name="SchedulingAssistant",
    model=MODEL,
    description="Agent for calculating realistic timelines based on resource bandwidth and task priority in Logseq.",
    instruction=get_scheduling_instruction,
    before_agent_callback=[load_logseq_schema_callback],
    tools=[
        fetch_workload_and_resources_tool,
        apply_scheduling_results_tool
    ]
)
