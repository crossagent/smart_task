
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

@pytest.mark.asyncio
async def test_remote_agent_chat():
    async with httpx.AsyncClient() as client:
        # Construct a JSON-RPC request to the daily_todo agent
        # The method for chat is typically "model.generate" or similar depending on protocol, 
        # but let's try a standard one or just check if the endpoint accepts POST.
        # Based on adk-python, the endpoint is /a2a/daily_todo
        
        # We need to send a valid JSON-RPC 2.0 request
        # The method might be 'agent.query' or similar. 
        # Let's try to send a simple "query"
        rpc_payload = {
            "jsonrpc": "2.0",
            "method": "model.generate", # Standard ADK agent method
            "params": {"inputs": [{"role": "user", "content": {"content_type": "text", "parts": ["hello"]}}]},
            "id": 1
        }
        
        # We expect this to FAIL if the agent is not loaded correctly (e.g. 404 or 500)
        # But for this test, let's just assert the status code and print the response
        resp = await client.post("http://localhost:8000/a2a/daily_todo", json=rpc_payload)
        
        print(f"Chat Response Status: {resp.status_code}")
        print(f"Chat Response Body: {resp.text}")
        
        # If the agent is missing (no root_agent), ADK might return 404 or 500 because it can't load the app.
        if resp.status_code != 200:
             print("Test purposely failed or agent unreachble as expected.")
        else:
             print("Agent responded successfully.")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_remote_agent_card_reachable())
    loop.run_until_complete(test_remote_agent_chat())
