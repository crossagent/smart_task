import logging
import time
from typing import List, Dict, Any, Optional
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.events.event import Event, EventActions

class AgentTestClient:
    """
    A test-specific client that captures all agent events.
    adapted from AdkSimulationClient.
    """

    def __init__(self, agent: LlmAgent, app_name: str = "test_app"):
        if not agent:
             raise ValueError("Agent must be provided")
        
        self.app_name = app_name
        self.agent = agent
        self.session_service = InMemorySessionService()
        self.artifact_service = InMemoryArtifactService()
        self.user_id: str = "default_user"
        self.session_id: str = None
        self.session = None

    async def create_new_session(self, user_id: str, session_id: str, initial_state: Dict[str, Any] = None) -> str:
        self.user_id = user_id
        self.session_id = session_id
        self.session = await self.session_service.create_session(
            app_name=self.app_name, 
            user_id=user_id, 
            session_id=session_id,
            state=initial_state
        )
        return self.session.id

    async def chat(self, user_text: str) -> List[str]:
        if not self.session: raise RuntimeError("No active session.")
        
        responses = []
        
        async with Runner(
            app_name=self.app_name,
            agent=self.agent,
            session_service=self.session_service,
            artifact_service=self.artifact_service,
        ) as runner:
            
            message = types.Content(role="user", parts=[types.Part(text=user_text)])
            
            print("\n[TestClient] Sending Message...")
            async for event in runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=message
            ):
                print(f"  -> Event: author='{event.author}' type={type(event)}")
                if event.content:
                    for p in event.content.parts:
                        try:
                            print(f"     Part: {repr(p)}")
                        except UnicodeEncodeError:
                             print("     Part: [Content cannot be printed in current console encoding]")
                
                # Logic: Capture text from the agent (author needs to match agent name or be 'model'?)
                # We accept both to be safe.
                if (event.author == self.agent.name or event.author == "model") and event.content:
                    for p in event.content.parts:
                        if p.text:
                            responses.append(p.text)
                        if p.function_call:
                            print(f"     [Tool Call] {p.function_call.name}")

        return responses
