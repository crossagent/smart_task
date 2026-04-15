import os
import sys

# Ensure we can import DB tools
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.task_management.tools import upsert_resource

# Define the 6 teams
teams = [
    {
        "id": "RES-RESEARCHER",
        "name": "Quant Researcher",
        "role": "Alpha Research / Strategy",
        "port": 9013,
        "service": "researcher_agent",
        "workspace": "/workspaces/researcher"
    },
    {
        "id": "RES-TESTER",
        "name": "QA Tester",
        "role": "Quality Assurance / Backtest Verify",
        "port": 9014,
        "service": "tester_agent",
        "workspace": "/workspaces/tester"
    },
    {
        "id": "RES-TRADER",
        "name": "Execution Trader",
        "role": "Order Execution / Trading",
        "port": 9015,
        "service": "trader_agent",
        "workspace": "/workspaces/trader"
    },
    {
        "id": "RES-ANALYST",
        "name": "Data Analyst",
        "role": "Data Ingestion / Analysis",
        "port": 9016,
        "service": "analyst_agent",
        "workspace": "/workspaces/analyst"
    },
    {
        "id": "RES-RISK",
        "name": "Risk Manager",
        "role": "Risk Control / Capital Safety",
        "port": 9017,
        "service": "risk_manager_agent",
        "workspace": "/workspaces/risk"
    },
    {
        "id": "RES-DEVOPS",
        "name": "Infra DevOps",
        "role": "Infrastructure / Sentry",
        "port": 9018,
        "service": "devops_agent",
        "workspace": "/workspaces/devops"
    }
]

print("Registering 6 Quant Departments into STH Database...")

for team in teams:
    url = f"http://{team['service']}:{team['port']}"
    # Using upsert_resource tool logic
    # Note: In the tool, workspace_path is for the internal container mapping if needed, 
    # but the Agent itself is a Remote entity. 
    # We store the URL in the agent_dir field if we wanted but the tool has agent_dir for local.
    # Actually, let's just make sure we store it correctly for the scheduler.
    # Wait, looking at scheduler.py, it uses agent_url if available.
    
    # Let's check resources table schema again to see where URL goes.
    pass

# Actually, I'll use raw SQL to ensure agent_url is set correctly if the tool doesn't support it yet.
from src.task_management.db import execute_mutation

sql = """
    INSERT INTO resources (id, name, org_role, resource_type, agent_dir, workspace_path, is_available)
    VALUES (%s, %s, %s, 'agent', %s, %s, true)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        org_role = EXCLUDED.org_role,
        agent_dir = EXCLUDED.agent_dir,
        workspace_path = EXCLUDED.workspace_path,
        is_available = true
"""

for team in teams:
    # We use agent_dir to store the base URL for Remote ADK agents in this architecture
    url = f"http://{team['service']}:{team['port']}"
    try:
        execute_mutation(sql, (team['id'], team['name'], team['role'], url, team['workspace']))
        print(f"Success: Registered {team['name']} at {url}")
    except Exception as e:
        print(f"Error registering {team['id']}: {e}")

print("Registration complete.")
