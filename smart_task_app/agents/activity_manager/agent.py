from __future__ import annotations
import os
import subprocess
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from smart_task_app.shared_libraries.constants import MODEL
from smart_task_app.shared_libraries.plugins import MaxTurnsPlugin

# Global MCP中枢地址 (Docker内部网桥地址)
STH_MCP_URL = "http://smart_task_copilot:45666/mcp"

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
    description="Activity Manager (分解专家): 负责对 Project 进行原子化任务拆解与架构定义，统筹员工执行。",
    instruction=f"""You are the Activity Manager in the Smart Task Hub.
Your responsibilities include:
1. Writing design docs using 'write_module_design_doc'.
2. Browsing the database schema or querying existing data via 'get_database_schema' or 'query_sql' (from MCP).
3. Recording split tasks into the STH database using 'upsert_task' (from MCP).
4. Defining clear module_iteration_goals and correct depends_on strings (e.g. '{{TSK-001,TSK-002}}').
5. Finally, use 'submit_task_deliverable' (from MCP) to mark your own management task as 'code_done'.

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
