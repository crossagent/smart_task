from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from ...model.state import TaskState

class DueDateEstimator(BaseAgent):
    """
    Agent responsible for estimating a due date if missing.
    """
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state_dict = ctx.session.state.get("task_state", {})
        if not state_dict: return
        state = TaskState(**state_dict)

        if "due_date" in state.missing_fields:
            print(f"[{self.name}] Inferring due date...")
            # Mock inference
            suggestion = "Tomorrow"
            state.inference_candidates["due_date"] = suggestion
            print(f"[{self.name}] Suggested due_date: {suggestion}")
            
            # Update state
            ctx.session.state["task_state"] = state.__dict__
            yield Event(
                author=self.name, 
                content=types.Content(parts=[types.Part(text=f"Suggested due_date: {suggestion}")])
            )
