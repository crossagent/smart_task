import asyncio
import logging
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from .add_task.agent import AddTaskWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "smart_task"
USER_ID = "user_123"
SESSION_ID = "session_1"

async def main():
    # 初始化工作流 - 现在使用工厂函数
    agent = AddTaskWorkflow()
    
    # Setup session service
    session_service = InMemorySessionService()
    
    # 创建初始session,用户输入存储在user_input字段
    initial_state = {
        "user_input": "安排明天的会议",  # 测试输入
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
    
    # 运行工作流
    # 发送一个触发消息,实际的用户输入在session.state["user_input"]中
    content = types.Content(role='user', parts=[types.Part(text="Start workflow")])
    
    logger.info("Starting AddTask workflow...")
    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=content):
        if event.author:
             logger.info(f"Event from {event.author}:")
             if event.content and event.content.parts:
                 for part in event.content.parts:
                     logger.info(f"  Content: {part.text}")

    # Check final state
    final_session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    print("\n--- Final Session State ---")
    for key, value in final_session.state.items():
        print(f"{key}: {value}")

if __name__ == "__main__":
    asyncio.run(main())

