from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from src.model.state import TaskState

class IntakeRouter(BaseAgent):
    """
    Agent responsible for initial parsing of user input to identify intent and extract basic fields.
    """
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Retrieve state
        state_dict = ctx.session.state.get("task_state", {})
        
        # If state is empty, initialize it
        if not state_dict:
            # We expect 'user_input' to be in the session state initially
            user_input = ctx.session.state.get("user_input", "")
            state = TaskState(user_input=user_input)
        else:
            # Reconstruct state (simplified)
            state = TaskState(**state_dict)

        print(f"[{self.name}] Processing input: {state.user_input}")
        
        # Mock parsing logic
        if "meeting" in state.user_input.lower():
            state.parsed_fields["title"] = state.user_input
            state.parsed_fields["type"] = "meeting"
        else:
            state.parsed_fields["title"] = state.user_input
            state.parsed_fields["type"] = "task"
            
        print(f"[{self.name}] Parsed fields: {state.parsed_fields}")
        
        # Save state back to session
        ctx.session.state["task_state"] = state.__dict__
        
        yield Event(
            author=self.name, 
            content=types.Content(parts=[types.Part(text=f"Intake complete. Parsed: {state.parsed_fields}")])
        )
