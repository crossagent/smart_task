import sys
import os
import asyncio

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import ADK
try:
    from google.adk.a2a.utils.agent_card_builder import AgentCardBuilder
except ImportError:
    print("Error: google.adk.a2a.utils.agent_card_builder not found.")
    sys.exit(1)

# Import Agent Instances
import traceback
try:
    from smart_task_app.root_agent.agent import agent as root_agent
    from smart_task_app.new_task.agent import new_task_agent
    from smart_task_app.daily_todo.agent import daily_todo_agent
except Exception:
    traceback.print_exc()
    sys.exit(1)

AGENTS = [
    (root_agent, "smart_task_app/root_agent/agent.json"),
    (new_task_agent, "smart_task_app/new_task/agent.json"),
    (daily_todo_agent, "smart_task_app/daily_todo/agent.json"),
]

async def generate_card(agent, rel_path):
    print(f"Generating card for {agent.name}...")
    
    # Construct RPC URL (assuming standard A2A pattern)
    rpc_url = f"http://localhost:8000/a2a/{agent.name}"
    
    builder = AgentCardBuilder(
        agent=agent,
        rpc_url=rpc_url,
        agent_version="0.0.1"
    )
    
    card = await builder.build()
    
    output_path = os.path.join(project_root, rel_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        # User requested model_dump_json (Pydantic v2 style)
        if hasattr(card, "model_dump_json"):
             f.write(card.model_dump_json(indent=2, exclude_none=True))
        else:
             f.write(card.json(indent=2, exclude_none=True))
        
    print(f"✅ Generated {output_path}")

async def main():
    tasks = [generate_card(agent, path) for agent, path in AGENTS]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
