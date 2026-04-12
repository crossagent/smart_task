import sys
import os
import time
import httpx
import logging
from typing import Optional

from dotenv import load_dotenv

# Ensure src is in path
sys.path.append(os.getcwd())

# Load environment variables from .env
load_dotenv()

# Force DB_PORT for host connection
os.environ["DB_PORT"] = "5433"

from src.task_management.db import execute_mutation, execute_query
from src.resource_management.supervisor import AgentSupervisor

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("functional_test")

def setup_test_data():
    logger.info("Cleaning up and setting up test data...")
    execute_mutation("DELETE FROM tasks WHERE id LIKE 'TSK-WIN-TEST%'")
    execute_mutation("DELETE FROM modules WHERE id = 'MOD-WIN-TEST'")
    execute_mutation("DELETE FROM activities WHERE id = 'ACT-WIN-TEST'")
    execute_mutation("DELETE FROM projects WHERE id = 'PRJ-WIN-TEST'")
    execute_mutation("DELETE FROM resources WHERE id = 'RES-ARCHITECT-001'")
    
    # 1. Resource
    execute_mutation("""
        INSERT INTO resources (id, name, org_role, is_available, resource_type, agent_dir)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET is_available = EXCLUDED.is_available
    """, ("RES-ARCHITECT-001", "WinArchitect", "Architect", True, "agent", "smart_task_app/agents/architect"))
    
    # 2. Project
    execute_mutation("""
        INSERT INTO projects (id, name, initiator_res_id, status, memo_content)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
    """, ("PRJ-WIN-TEST", "Windows Test Project", "RES-ARCHITECT-001", "Active", "Test context for Windows functional flow."))
    
    # 3. Activity
    execute_mutation("""
        INSERT INTO activities (id, project_id, name, owner_res_id, status)
        VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING
    """, ("ACT-WIN-TEST", "PRJ-WIN-TEST", "Design Demo", "RES-ARCHITECT-001", "Active"))
    
    # 4. Module
    execute_mutation("""
        INSERT INTO modules (id, name, owner_res_id)
        VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING
    """, ("MOD-WIN-TEST", "DemoModule", "RES-ARCHITECT-001"))
    
    # 5. Task
    execute_mutation("""
        INSERT INTO tasks (id, module_id, resource_id, module_iteration_goal, activity_id, project_id, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, ("TSK-WIN-TEST-001", "MOD-WIN-TEST", "RES-ARCHITECT-001", 
          "Break down a simple Hello World CLI app into 2 tasks: 1. Setup project 2. Implement logic.",
          "ACT-WIN-TEST", "PRJ-WIN-TEST", "ready"))
    
    logger.info("Test data setup complete.")

def monitor_test(task_id: str, timeout=120):
    logger.info(f"Monitoring task {task_id} for completion...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Check main task status
        res = execute_query("SELECT status FROM tasks WHERE id = %s", (task_id,))
        status = res[0]['status'] if res else "NOT_FOUND"
        
        # Check for subtasks
        subtasks = execute_query("SELECT id, module_iteration_goal FROM tasks WHERE id LIKE 'TSK-WIN-TEST%%' AND id != %s", (task_id,))
        
        logger.info(f"Current Status: {status} | Subtasks found: {len(subtasks)}")
        
        if status == 'code_done':
            logger.info("SUCCESS: Architect marked the task as done!")
            if subtasks:
                logger.info("Found child tasks:")
                for st in subtasks:
                    logger.info(f"  - {st['id']}: {st['module_iteration_goal']}")
            return True
            
        time.sleep(10)
    
    logger.error("TIMEOUT: Task did not complete in time.")
    return False

def run_functional_test():
    setup_test_data()
    
    # Start the pool
    supervisor = AgentSupervisor(config_path="config_win.yaml")
    supervisor.bootstrap()
    
    time.sleep(10) # Wait for initial process spawn
    
    try:
        # Check if ports are open before sending invocation
        logger.info("Waiting for Agent API to be ready (Polling http://localhost:9011/)...")
        ready = False
        for i in range(12): # Wait up to 60 seconds
            try:
                with httpx.Client(timeout=5.0) as client:
                    resp = client.get("http://localhost:9011/")
                    if resp.status_code < 500:
                        ready = True
                        break
            except Exception:
                pass
            logger.info(f"  Attempt {i+1}/12: still waiting...")
            time.sleep(5)
            
        if not ready:
            logger.error("Architect Agent failed to reach READY state in time.")
            return

        # NEW: Explicitly create session before /run
        logger.info("Initializing session for Architect...")
        session_url = "http://localhost:9011/apps/architect/users/test-user/sessions"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(session_url, json={"session_id": "TSK-WIN-TEST-001"})
                if resp.status_code in (200, 201, 409):
                    logger.info("Session ready (created or already exists).")
                else:
                    logger.error(f"Failed to create session: {resp.status_code} {resp.text}")
                    return
        except Exception as e:
            logger.error(f"Session initialization error: {e}")
            return

        # Dispatch the invocation manually
        logger.info("Sending invocation to Architect at localhost:9011/run...")
        payload = {
            "app_name": "architect",
            "user_id": "test-user",
            "session_id": "TSK-WIN-TEST-001",
            "new_message": {"parts": [{"text": "Current Task ID: TSK-WIN-TEST-001. Please perform the breakdown and record it in STH."}]}
        }
        
        # Retry POST if 503
        for i in range(3):
            try:
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post("http://localhost:9011/run", json=payload)
                    if resp.status_code == 200:
                        logger.info("Invocation accepted and processed.")
                        break
                    elif resp.status_code == 503:
                        logger.warning(f"  Attempt {i+1}/3: 503 Service Unavailable, retrying in 5s...")
                        time.sleep(5)
                    else:
                        logger.error(f"Failed to dispatch: {resp.status_code} {resp.text}")
                        break
            except Exception as e:
                logger.error(f"Failed to dispatch on attempt {i+1}: {e}")
                if i == 2: return
                time.sleep(5)

        # Monitor DB
        monitor_test("TSK-WIN-TEST-001")
        
    finally:
        logger.info("Shutting down supervisor...")
        supervisor.stop()

if __name__ == "__main__":
    run_functional_test()
