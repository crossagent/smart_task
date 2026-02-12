
import pytest
import httpx
import asyncio
from smart_task_app.agent import root_agent
# Assuming AgentTestClient or similar is available, otherwise use direct agent interaction if possible
# But RemoteA2aAgent inside root_agent needs an execution environment.

# Simple check: can we reach the agent card?
@pytest.mark.asyncio
async def test_remote_agent_card_reachable():
    async with httpx.AsyncClient() as client:
        # Check AddTaskOrchestrator card
        resp = await client.get("http://localhost:8000/a2a/new_task/.well-known/agent-card.json")
        assert resp.status_code == 200, f"Failed to reach new_task agent card. Status: {resp.status_code}"
        data = resp.json()
        assert data['name'] == "AddTaskOrchestrator"
        print("Successfully verified generic agent card reachability.")

        # Check DailyTodoAgent card
        resp = await client.get("http://localhost:8000/a2a/daily_todo/.well-known/agent-card.json")
        assert resp.status_code == 200, f"Failed to reach daily_todo agent card. Status: {resp.status_code}"
        data = resp.json()
        assert data['name'] == "DailyTodoAgent"
        print("Successfully verified daily_todo agent card reachability.")

if __name__ == "__main__":
    # Allow running directly for quick check
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_remote_agent_card_reachable())
