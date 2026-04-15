from __future__ import annotations
import logging
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

logger = logging.getLogger("smart_task.plugins.safety")

class MaxTurnsPlugin(BasePlugin):
    """
    Ensures an agent does not exceed a maximum number of turns in a single invocation.
    Prevents infinite tool-calling loops.
    """
    def __init__(self, max_turns: int = 3):
        super().__init__(name="max_turns_safety")
        self.max_turns = max_turns

    async def before_run_callback(self, *, invocation_context: InvocationContext) -> types.Content | None:
        # Check current turn count in this invocation
        # ADK keeps events in invocation_context.session.events
        invocation_id = invocation_context.invocation_id
        turns = [e for e in invocation_context.session.events if e.invocation_id == invocation_id and e.author != 'user']
        
        if len(turns) >= self.max_turns:
            logger.warning(f"Safety Triggered: Invocation {invocation_id} reached max turns ({self.max_turns}). Terminating.")
            return types.Content(
                role="model",
                parts=[types.Part(text=f"ERROR: Execution terminated by MaxTurnsPlugin. Reached maximum safety limit of {self.max_turns} turns.")]
            )
        return None
