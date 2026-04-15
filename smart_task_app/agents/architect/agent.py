from __future__ import annotations

import os
import psycopg2
from google.adk.agents import LlmAgent
from smart_task_app.shared_libraries.constants import MODEL

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        dbname=os.getenv("DB_NAME", "smart_task_hub"),
        user=os.getenv("DB_USER", "smart_user"),
        password=os.getenv("DB_PASSWORD", "smart_pass")
    )

def write_module_design_doc(module_name: str, content: str) -> str:
    """Writes the architectural design document for a module to the docs directory and commits it using git."""
    try:
        import subprocess
        # Get the root path of the project (assuming smart_task_app is at root level /smart_task)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        docs_dir = os.path.join(project_root, "docs", module_name)
        os.makedirs(docs_dir, exist_ok=True)
        file_path = os.path.join(docs_dir, f"{module_name}_design.md")
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Perform git add and commit
        subprocess.run(["git", "add", file_path], cwd=project_root, check=True)
        subprocess.run(["git", "commit", "-m", f"docs: Architect updated design for module {module_name}"], cwd=project_root, check=True)
            
        return f"Successfully wrote and committed design document to {file_path}"
    except Exception as e:
        return f"Error writing or committing document: {e}"

from typing import List

def record_task_in_sth(
    task_id: str, 
    module_id: str, 
    resource_id: str, 
    module_iteration_goal: str,
    estimated_hours: float,
    depends_on: List[str] = []
) -> str:
    """Records a new broken-down task into the STH database."""
    if depends_on is None:
        depends_on = []
    
    # Needs to be a string format for postgres '{id1,id2}'
    depends_on_str = "{" + ",".join(depends_on) + "}"
    
    sql = """
    INSERT INTO tasks (id, module_id, resource_id, module_iteration_goal, estimated_hours, depends_on, status)
    VALUES (%s, %s, %s, %s, %s, %s, 'pending')
    ON CONFLICT (id) DO UPDATE SET
        module_id = EXCLUDED.module_id,
        resource_id = EXCLUDED.resource_id,
        module_iteration_goal = EXCLUDED.module_iteration_goal,
        estimated_hours = EXCLUDED.estimated_hours,
        depends_on = EXCLUDED.depends_on
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (task_id, module_id, resource_id, module_iteration_goal, estimated_hours, depends_on_str))
                conn.commit()
        return f"Task {task_id} recorded in STH successfully."
    except Exception as e:
        return f"DB error while recording task: {e}"

def mark_architect_task_done(task_id: str) -> str:
    """Marks the architect's own assignment task as code_done after completing the breakdown."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE tasks SET status = 'code_done' WHERE id = %s", (task_id,))
                conn.commit()
        return f"Architect Activity Task {task_id} marked as code_done."
    except Exception as e:
        return f"Error: {e}"

from google.adk.apps import App
from google.adk.plugins.logging_plugin import LoggingPlugin

root_agent = LlmAgent(
    name="architect",
    model=MODEL,
    description="Architect Agent (分解专家): 负责对 Project 进行原子化任务拆解与架构定义",
    instruction="""You are the Architect Agent in the Smart Task Hub.
If a task ID is provided via the SMART_TASK_ID environment variable, decompose that specific work into smaller modules/tasks.
If NO task ID is provided, you should act on the direct instructions provided in the message.
Your responsibilities include:
1. Writing design docs using write_module_design_doc (which automatically commits to Git).
2. Recording split tasks into the STH database using record_task_in_sth.
3. Defining clear module_iteration_goals and correct depends_on arrays (DAG).
4. Estimating the effort using estimated_hours for each child task (e.g. 2.5, 4.0).
Finally, if a task ID was provided, mark your task status to 'code_done' using mark_architect_task_done.
""",
    tools=[write_module_design_doc, record_task_in_sth, mark_architect_task_done]
)

app = App(
    name="architect",
    root_agent=root_agent,
    plugins=[]  # Temporarily disabled LoggingPlugin to bypass Windows GBK encoding issues
)
