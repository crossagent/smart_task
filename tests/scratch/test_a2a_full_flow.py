import os
import time
import httpx
import logging
import asyncio
from dotenv import load_dotenv
from src.resource_management.supervisor import AgentSupervisor
from src.task_management.db import execute_query, execute_mutation

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_test_data(task_id: str):
    execute_mutation("INSERT INTO resources (id, name, resource_type, is_available, org_role, status) VALUES ('RES-ROOT-COORD-001', 'Root Coordinator', 'agent', true, 'Manager', 'Available') ON CONFLICT DO NOTHING")
    execute_mutation("INSERT INTO modules (id, name, owner_res_id, status) VALUES ('ROOT-SYSTEM', 'Root System', 'RES-ROOT-COORD-001', 'Active') ON CONFLICT DO NOTHING")
    execute_mutation("DELETE FROM tasks WHERE id LIKE 'TSK-A2A%'")
    execute_mutation(
        "INSERT INTO tasks (id, module_id, resource_id, module_iteration_goal, status) VALUES (%s, %s, %s, %s, %s)",
        (task_id, "ROOT-SYSTEM", "RES-ROOT-COORD-001", "Full A2A Pipeline Test: Design and Implement a dummy feature.", "ready")
    )
    logger.info("Test data setup complete.")

def run_a2a_test():
    load_dotenv()
    task_id = "TSK-A2A-TEST-001"
    setup_test_data(task_id)
    
    config_path = "config_win.yaml"
    supervisor = AgentSupervisor(config_path)
    
    try:
        logger.info("Bootstrapping A2A Agent Pool (Main: 9010, Arch: 9011, Code: 9012)...")
        supervisor.bootstrap()
        
        # Wait for agents to be ready
        logger.info("Waiting for Cluster (9010, 9011, 9012) to be ready...")
        ready_ports = []
        for port in [9011, 9012, 9010]:
            port_ready = False
            for _ in range(15):
                try:
                    with httpx.Client(timeout=2.0) as client:
                        resp = client.get(f"http://localhost:{port}/")
                        if resp.status_code < 500:
                            port_ready = True
                            break
                except: pass
                time.sleep(3)
            if port_ready: ready_ports.append(port)
        
        if len(ready_ports) < 3:
            logger.error(f"Not all agents are ready. Ready ports: {ready_ports}")
            return

        # Initialize session for Main Coordinator
        logger.info("Initializing session for Coordinator...")
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post("http://localhost:9010/apps/smart_task_app/users/test-user/sessions", json={"session_id": task_id})
        except Exception as e:
            logger.warning(f"Session init warning: {e}")

        # Trigger A2A Flow
        logger.info(f"Triggering A2A workflow for {task_id} via port 9010...")
        payload = {
            "app_name": "smart_task_app",
            "user_id": "test-user",
            "session_id": task_id,
            "new_message": {"parts": [{"text": f"Please coordinate the breakdown and implementation for task {task_id}. Break it down into modules and then implement them."}]}
        }
        
        with httpx.Client(timeout=300.0) as client: # LONG timeout for multi-agent chain
            resp = client.post("http://localhost:9010/run", json=payload)
            if resp.status_code == 200:
                logger.info("A2A Sequence completed/started successfully.")
            else:
                logger.error(f"Failed to start A2A: {resp.status_code}")
                logger.error(f"Error Details: {resp.text}")
                return

        # Monitor DB for changes
        logger.info("Monitoring DB for A2A results (Expect subtasks and status updates)...")
        for i in range(24): # 2 minutes
            res = execute_query("SELECT id, status FROM tasks WHERE id = %s", (task_id,))
            subtasks = execute_query("SELECT id, status FROM tasks WHERE id LIKE 'TSK-A2A%' AND id != %s", (task_id,))
            
            status = res[0]['status'] if res else "NOT_FOUND"
            logger.info(f"Check {i+1}/24: Root Status: {status} | Subtasks: {len(subtasks)}")
            
            # If subtasks created and root task evolved or coder finished something
            if len(subtasks) > 0:
                logger.info("Success! A2A Architect correctly decomposed the task.")
                # We can stop early if we see progress
                # Standard Sequential finish: both agents processed.
                
            time.sleep(5)

    finally:
        logger.info("Shutting down supervisor...")
        supervisor.stop()

if __name__ == "__main__":
    run_a2a_test()
