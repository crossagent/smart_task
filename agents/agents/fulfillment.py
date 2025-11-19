from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from ..model.state import TaskState

class Fulfillment(BaseAgent):
    """
    Agent responsible for fulfilling the task (saving it).
    """
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state_dict = ctx.session.state.get("task_state", {})
        if not state_dict: return
        state = TaskState(**state_dict)
        
        print(f"[{self.name}] Fulfilling task...")
        
        # Mock fulfillment
        # In a real scenario, this would write to a database
        final_task = {
            "title": state.parsed_fields.get("title"),
            "project": state.parsed_fields.get("project") or state.inference_candidates.get("project"),
            "due_date": state.parsed_fields.get("due_date") or state.inference_candidates.get("due_date"),
            "priority": state.parsed_fields.get("priority") or state.inference_candidates.get("priority"),
            "status": "created"
        }
        
        print(f"[{self.name}] Task created: {final_task}")
        
        yield Event(
            author=self.name, 
            content=types.Content(parts=[types.Part(text=f"Task fulfilled: {final_task}")])
        )
