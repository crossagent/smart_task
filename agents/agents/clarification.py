from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from ..model.state import TaskState

class ClarificationSynthesizer(BaseAgent):
    """
    Agent responsible for generating clarification questions.
    """
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state_dict = ctx.session.state.get("task_state", {})
        if not state_dict: return
        state = TaskState(**state_dict)
        
        print(f"[{self.name}] Synthesizing clarification questions...")
        
        questions = []
        for field in state.missing_fields:
            if field in state.inference_candidates:
                suggestion = state.inference_candidates[field]
                questions.append(f"Is the {field} '{suggestion}'?")
            else:
                questions.append(f"What is the {field}?")
        
        state.clarification_questions = questions
        print(f"[{self.name}] Questions: {state.clarification_questions}")
        
        # Update state
        ctx.session.state["task_state"] = state.__dict__
        yield Event(
            author=self.name, 
            content=types.Content(parts=[types.Part(text=f"Clarification questions: {questions}")])
        )
