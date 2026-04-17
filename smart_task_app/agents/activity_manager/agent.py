from __future__ import annotations
import os
import subprocess
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL, GLOBAL_LANGUAGE_INSTRUCTION
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin

# Global MCP中枢地址 (Docker内部网桥地址)
STH_MCP_URL = "http://smart_task_copilot:45666/mcp/"

def write_module_design_doc(module_name: str, content: str) -> str:
    """Writes the architectural design document for a module to the docs directory and commits it using git."""
    try:
        # Get the root path of the project (assuming smart_task_app is at root level /smart_task)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        docs_dir = os.path.join(project_root, "docs", module_name)
        os.makedirs(docs_dir, exist_ok=True)
        file_path = os.path.join(docs_dir, f"{module_name}_design.md")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Perform git add and commit
        subprocess.run(["git", "add", file_path], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", f"docs: Activity Manager updated design for module {module_name}"], cwd=project_root, check=True)
            
        return f"Successfully wrote and committed design document to {file_path}"
    except Exception as e:
        return f"Error writing or committing document: {e}"

root_agent = LlmAgent(
    name="activity_manager",
    model=MODEL,
    description="Activity Manager (Control Plane): 负责全系统的架构治愈与任务调度，在系统中断时唤醒进行现场诊断。",
    instruction=f"""You are the Activity Manager and System Control Plane in the Smart Task Hub.
You act as a supervisor sitting on the System Event Bus.

Your responsibilities include:
1. Handling System Interrupts (Tasks prefixed with 'INT-EVT-'): 
   - When awakened by an interrupt, analyze the execution state of the DAG.
   - Use 'query_sql' to see the logs and blocker_reason of the failed node.
   - Heal the system: You can rewrite the goal of a blocked task, split it into new tasks, or reset its status to ‘ready’/‘pending’.
2. Architectural Design: Writing design docs using 'write_module_design_doc'.
3. Task Orchestration: Recording/splitting tasks using 'upsert_task' and defining dependencies.
4. Multi-Interrupt Handling: Look for the '[SYSTEM] PARALLEL INTERRUPTS DETECTED: [ID1, ID2...]' marker in your goal.
   - If present, use 'get_task_details' to read the logs and goals of all listed IDs.
   - Treat all listed interrupts as a single strategic context and provide one consolidated plan to solve them all.
5. Finally, use 'submit_task_deliverable' to mark the current Interrupt or Task as 'code_done'.

{GLOBAL_LANGUAGE_INSTRUCTION}

Note: Database tools are provided via the centralized MCP server at {STH_MCP_URL}.
""",
    tools=[
        write_module_design_doc,
        McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=STH_MCP_URL)
        )
    ]
)

app = App(
    name="activity_manager",
    root_agent=root_agent,
    plugins=[MaxTurnsPlugin(max_turns=3)]
)
