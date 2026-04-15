from __future__ import annotations
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from google.adk.agents import LlmAgent
from google.adk.apps import App
import threading

# Configuration
DEPARTMENT_NAME = os.getenv("DEPARTMENT_NAME", "Unknown Department")
MAX_SECONDS = int(os.getenv("MAX_SECONDS", "300"))
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smart_task_hub")
DB_USER = os.getenv("DB_USER", "smart_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "smart_pass")
# Workspace path inside container
LOG_PATH = "/workspaces/work_log.txt"

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def stay_busy(task_id: str, goal: str) -> str:
    """Simulates realistic work for the assigned task, writing heartbeats to logs."""
    
    # 1. Self-Estimation: Query actual duration from Task DB
    duration = 30 # Default safety
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT estimated_hours FROM tasks WHERE id = %s", (task_id,))
                res = cursor.fetchone()
                if res and res['estimated_hours']:
                    # Convert hours to seconds for this mock (scaled for faster testing)
                    # e.g., 1 hour = 60 seconds mock time
                    duration = float(res['estimated_hours']) * 60 
    except Exception as e:
        print(f"Error querying estimation: {e}")

    # 2. Hard Cap at 300s
    duration = min(duration, MAX_SECONDS)
    if duration < 10: duration = 10 # Min 10s for observation

    print(f"Starting work on {task_id} for {duration} seconds...")

    # 3. Work Loop (Heartbeat)
    start_time = time.time()
    try:
        # Ensure directory exists for log
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        
        while time.time() - start_time < duration:
            elapsed = int(time.time() - start_time)
            percent = int((elapsed / duration) * 100)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"[{timestamp}] [{DEPARTMENT_NAME}] WORKING ON [{task_id}]: {percent}% | Goal: {goal}\n"
            
            with open(LOG_PATH, "a") as f:
                f.write(log_line)
            
            time.sleep(1)
            
    except Exception as e:
        return f"Worker Error: {str(e)}"

    # 4. Finalize Task in DB
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE tasks SET status = 'code_done', updated_at = CURRENT_TIMESTAMP WHERE id = %s", 
                    (task_id,)
                )
                conn.commit()
    except Exception as e:
        return f"Work finished but DB update failed: {e}"

    return f"Mission Accomplished! Task {task_id} finished in {int(duration)}s."

# ADK Agent Definition
root_agent = LlmAgent(
    name="mock_worker",
    model="gemini-2.5-flash", 
    description=f"Virtual Worker for {DEPARTMENT_NAME}",
    instruction=f"You are the {DEPARTMENT_NAME} Agent. Your only job is to STAY BUSY using the stay_busy tool whenever you receive a Task ID.",
    tools=[stay_busy]
)

app = App(
    name="mock_worker",
    root_agent=root_agent
)
