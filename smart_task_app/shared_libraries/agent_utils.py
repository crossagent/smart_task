from __future__ import annotations
import os
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor

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
    """Executes a shell command. Runs in SMART_WORKSPACE_PATH if set."""
    try:
        cwd = os.getenv("SMART_WORKSPACE_PATH", os.getcwd())
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)

def submit_task_deliverable(task_id: str, status: str, execution_result: str) -> str:
    """Sets the task status (e.g. 'code_done') and provides a summary of the work done."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE tasks SET status = %s, execution_result = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", 
                    (status, execution_result, task_id)
                )
                conn.commit()
        return f"Task '{task_id}' marked as {status} with deliverables."
    except Exception as e:
        return str(e)

def report_blocker(task_id: str, reason: str) -> str:
    """Report a blocker or failure for a task."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE tasks SET status = 'failed', blocker_reason = %s WHERE id = %s", 
                    (reason, task_id)
                )
                conn.commit()
        return "Task marked as failed and blocker reported."
    except Exception as e:
        return str(e)
