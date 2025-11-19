from typing import AsyncGenerator
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from .workflows.add_task import AddTaskWorkflow


class DispatcherAgent(BaseAgent):
    """
    Dispatcher Agent - Routes user requests to appropriate workflows.
    Currently handles the 'add_task' workflow.
    """
    
    def __init__(self, name: str = "DispatcherAgent"):
        super().__init__(name=name)
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Main entry point for the dispatcher agent.
        Analyzes user input and routes to the appropriate workflow.
        """
        # Get user input - for ADK web it's typically in session state
        user_input = ""
       
        # Try session state first (works in both ADK web and runner)
        if "user_input" in ctx.session.state:
            user_input = ctx.session.state["user_input"]
        # Try new_message if available (Runner-based execution only)
        elif hasattr(ctx, 'new_message') and ctx.new_message:
            if hasattr(ctx.new_message, 'parts') and ctx.new_message.parts:
                user_input = ctx.new_message.parts[0].text
        
        if not user_input:
            user_input = "No input provided"
        
        print(f"[{self.name}] Received input: {user_input}")
        
        # Simple intent detection - currently only supports add_task
        # In the future, this could be expanded to route to different workflows
        intent = self._detect_intent(user_input)
        
        if intent == "add_task":
            # Route to AddTask workflow
            print(f"[{self.name}] Routing to AddTask workflow")
            
            # Initialize task state if not present
            if "task_state" not in ctx.session.state:
                ctx.session.state["task_state"] = {}
            if "user_input" not in ctx.session.state:
                ctx.session.state["user_input"] = user_input
            
            # Instantiate and delegate to the AddTask workflow
            workflow = AddTaskWorkflow()
            async for event in workflow._run_async_impl(ctx):
                yield event
        else:
            # Unknown intent
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(
                    text=f"I'm not sure how to handle that request. Currently I only support adding tasks."
                )])
            )
    
    def _detect_intent(self, user_input: str) -> str:
        """
        Simple intent detection logic.
        Currently defaults to 'add_task' for most inputs.
        """
        # Simple keyword-based intent detection
        # In production, this could use an LLM or more sophisticated NLU
        lower_input = user_input.lower()
        
        # For now, assume everything is an add_task request
        # unless it's clearly asking for something else
        return "add_task"
