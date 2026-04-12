import sys
import os
import time
import logging

# Ensure src is in path
sys.path.append(os.getcwd())

from src.resource_management.supervisor import AgentSupervisor

# Configure logging to see output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_win_bootstrap():
    print("Testing AgentSupervisor bootstrap on Windows...")
    
    # Initialize with Windows config
    supervisor = AgentSupervisor(config_path="config_win.yaml")
    
    try:
        # 1. Bootstrap the pool
        supervisor.bootstrap()
        
        # 2. Give it some time to start up
        print("Waiting 15 seconds for agents to start...")
        time.sleep(15)
        
        # 3. Check status
        for res_id, handle in supervisor.pool.items():
            status = "ALIVE" if handle.is_alive() else "DEAD"
            print(f"Agent {handle.agent_id} ({res_id}) on port {handle.port}: {status}")
            
            if not handle.is_alive():
                print(f"Warning: {handle.agent_id} failed to start. Check its logs.")
        
        # 4. Optional: check netstat (simulated by checking handles)
        print("\nBootstrap test completed. Press Ctrl+C to stop the pool or wait...")
        
        # Keep alive for a bit to see if they stay alive
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\nStopping pool...")
    finally:
        supervisor.stop()

if __name__ == "__main__":
    test_win_bootstrap()
