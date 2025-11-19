import asyncio
import logging
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from src.workflows.add_task import AddTaskWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "smart_task"
USER_ID = "user_123"
SESSION_ID = "session_1"

async def main():
    # Initialize the workflow agent
    agent = AddTaskWorkflow()
    
    # Setup session service
    session_service = InMemorySessionService()
    
    # Create initial session with user input
    # In a real app, this might come from a request
    initial_state = {
        "user_input": "Buy milk tomorrow",
        "task_state": {} # Initialize empty task state
    }
    
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state=initial_state
    )
    
    logger.info(f"Session created with state: {session.state}")
    
    # Setup runner
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    
    # Run the workflow
    # We send a dummy message to trigger the workflow, 
    # but our agents currently look at session state 'user_input'
    content = types.Content(role='user', parts=[types.Part(text="Start workflow")])
    
    logger.info("Starting workflow...")
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        if event.author:
             logger.info(f"Event from {event.author}:")
             if event.content and event.content.parts:
                 for part in event.content.parts:
                     logger.info(f"  Content: {part.text}")

    # Check final state
    final_session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print("\n--- Final Task State ---")
    print(final_session.state.get("task_state"))

if __name__ == "__main__":
    asyncio.run(main())
