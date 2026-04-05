from __future__ import annotations

import os
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor
from google.adk.agents.llm_agent import LlmAgent

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
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

root_agent = LlmAgent(
    name="coder_agent",
    model="gemini-2.5-flash",
    instruction="""You are the Coder Agent in the Smart Task Hub.
You will be provided a task ID via the SMART_TASK_ID environment variable.
Use the query_context tool to understand what you need to implement.
Perform the implementation natively. You have access to execute_shell which will execute bash/shell commands.
Verify your changes using `execute_shell('pytest')` if applicable.
Ensure you commit your work using git: `execute_shell('git add . && git commit -m "..."')`.
Finally, mark the task as completed using update_task_completed.
""",
    tools=[query_context, execute_shell, update_task_completed]
)
