from __future__ import annotations
import asyncio
import os
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

async def test_smoke():
    print("Testing A2A Connection to localhost:9013...")
    
    # Based on a2a.utils.constants, the path is /.well-known/agent-card.json
    agent_card_url = "http://localhost:9013/a2a/smoke_test/.well-known/agent-card.json"
    
    smoke_agent = RemoteA2aAgent(
        name="smoke_test",
        agent_card=agent_card_url
    )
    
    runner = Runner(
        app_name="agents",
        agent=smoke_agent,
        session_service=InMemorySessionService()
    )
    
    await runner.session_service.create_session(
        app_name="agents",
        user_id="test_user",
        session_id="test_session"
    )
    
    print(f"Running invocation against {agent_card_url}...")
    found_success = False
    
    new_message = types.Content(parts=[types.Part(text="Please use write_smoke_signal to write 'A2A_INFRA_OK'")])
    
    try:
        async for event in runner.run_async(
            user_id="test_user",
            session_id="test_session",
            new_message=new_message
        ):
            print(f"Event: {type(event).__name__}")
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"Text update: {part.text}")
                        if 'Successfully wrote' in part.text.lower() or 'a2a_infra_ok' in part.text.lower():
                            found_success = True
    except Exception as e:
        print(f"Error during run_async: {e}")
        import traceback
        traceback.print_exc()

    if found_success:
        print("\n[SUCCESS] A2A Infrastructure is verified!")
        if os.path.exists("smoke_signal.txt"):
            with open("smoke_signal.txt", "r") as f:
                content = f.read()
            print(f"Verified file content: {content}")
    else:
        print("\n[FAILED] Could not verify A2A response.")

if __name__ == "__main__":
    asyncio.run(test_smoke())
