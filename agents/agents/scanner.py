from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from ..model.state import TaskState

# Mock Schema for demonstration
REQUIRED_FIELDS = ["title", "project", "due_date", "priority"]

class SchemaScanner(BaseAgent):
    """
    Agent responsible for comparing parsed fields against the schema to identify missing fields.
    """
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state_dict = ctx.session.state.get("task_state", {})
        if not state_dict:
            return # Should not happen if Intake ran first
        state = TaskState(**state_dict)

        print(f"[{self.name}] Scanning schema for missing fields...")
        
        existing_keys = state.parsed_fields.keys()
        missing = [field for field in REQUIRED_FIELDS if field not in existing_keys]
        
        state.missing_fields = missing
        print(f"[{self.name}] Missing fields: {state.missing_fields}")
        
        ctx.session.state["task_state"] = state.__dict__
        
        yield Event(
            author=self.name, 
            content=types.Content(parts=[types.Part(text=f"Scan complete. Missing: {state.missing_fields}")])
        )
