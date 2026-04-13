from __future__ import annotations

import os
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
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

def query_context(task_id: str) -> str:
    """Gets the context for the task to be implemented in STH."""
    query = "SELECT module_iteration_goal, depends_on FROM tasks WHERE id = %s"
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query, (task_id,))
                res = cursor.fetchall()
                if not res: return "Task not found."
                return str(res[0])
    except Exception as e:
        return str(e)

def execute_shell(command: str) -> str:
    """Executes a shell command (git commit, pytest, etc). Runs in SMART_WORKSPACE_PATH if set."""
    try:
        cwd = os.getenv("SMART_WORKSPACE_PATH", os.getcwd())
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
        )
        return result.stdout + "\n" + result.stderr
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)

def update_task_completed(task_id: str) -> str:
    """Sets the task status to code_done, signaling completion."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE tasks SET status = 'code_done' WHERE id = %s", (task_id,))
                conn.commit()
        return "Task marked as code_done."
    except Exception as e:
        return str(e)

from google.adk.apps import App
from google.adk.plugins.logging_plugin import LoggingPlugin

root_agent = LlmAgent(
    name="coder",
    model=MODEL,
    description="Coder Agent (执行专家): 负责对 Architect 拆解的任务进行原子化代码实现与 DB 状态同步",
    instruction="""You are the Coder Agent in the Smart Task Hub.
If a task ID is provided via the SMART_TASK_ID environment variable, use the query_context tool to understand what you need to implement.
If NO task ID is provided, you should act on the direct instructions provided in the message from the user or the Architect.
Perform the implementation natively. You have access to execute_shell which will execute bash/shell commands (like 'ls', 'echo', 'touch').
Verify your changes using `execute_shell('pytest')` if applicable.
Ensure you commit your work using git: `execute_shell('git add . && git commit -m "..."')` if it's a code change.
Finally, if a task ID was provided, mark the task as completed using update_task_completed.
""",
    tools=[query_context, execute_shell, update_task_completed]
)

app = App(
    name="coder_app",
    root_agent=root_agent,
    plugins=[]  # Temporarily disabled LoggingPlugin to bypass Windows GBK encoding issues
)

