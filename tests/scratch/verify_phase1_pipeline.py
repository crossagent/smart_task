from __future__ import annotations
import asyncio
import os
import sys
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Ensure project root is in path
sys.path.append(os.getcwd())

from smart_task_app.agent import root_agent

async def test_pipeline():
    print("Testing SmartTaskPipeline with Distributed A2A Agents...")
    
    # We use a real Runner with the loaded root_agent (which contains RemoteA2aAgents)
    runner = Runner(
        app_name="agents", # Must match what RemoteA2aAgent infers
        agent=root_agent,
        session_service=InMemorySessionService()
    )
    
    await runner.session_service.create_session(
        app_name="agents",
        user_id="test_user",
        session_id="pipeline_test_session"
    )
    
    # Task: A simple request that triggers decomposition and implementation.
    task_desc = "Create a file named 'hello_a2a.txt' with the content 'Hello from Distributed A2A!'."
    new_message = types.Content(parts=[types.Part(text=task_desc)])
    
    print(f"Sending task to pipeline: {task_desc}")
    
    try:
        async for event in runner.run_async(
            user_id="test_user",
            session_id="pipeline_test_session",
            new_message=new_message
        ):
            # Print text events from agents
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        print(f"[{event.author}] {part.text}")
    except Exception as e:
        print(f"Error during pipeline execution: {e}")
        import traceback
        traceback.print_exc()

    # Verification: Check if the file was actually created by the Coder agent
    if os.path.exists("hello_a2a.txt"):
        with open("hello_a2a.txt", "r") as f:
            content = f.read()
        print(f"\n[SUCCESS] Pipeline verified! File content: {content}")
    else:
        print("\n[FAILED] hello_a2a.txt was not created.")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
