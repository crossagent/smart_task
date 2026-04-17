import logging
import httpx
import os
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types

logger = logging.getLogger("smart_task.plugins.safety")

# Hub Address (assumed stable internal Docker address)
HUB_URL = os.getenv("STH_HUB_URL", "http://smart_task_copilot:45666")

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
        invocation_id = invocation_context.invocation_id
        session = invocation_context.session
        turns = [e for e in session.events if e.invocation_id == invocation_id and e.author != 'user']
        
        if len(turns) >= self.max_turns:
            task_id = session.id
            logger.warning(f"Safety Triggered: Task {task_id} reached max turns ({self.max_turns}).")
            
            # Proactively notify Hub to mark task as blocked
            try:
                # Use a fire-and-forget approach or short timeout to avoid hanging the termination
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{HUB_URL}/api/task/{task_id}/block", 
                        params={"reason": f"MaxTurnsPlugin triggered ({self.max_turns} turns exceeded)"}
                    )
            except Exception as e:
                logger.error(f"Failed to notify Hub of blocked task {task_id}: {e}")

            return types.Content(
                role="model",
                parts=[types.Part(text=f"ERROR: Execution terminated by MaxTurnsPlugin. Reached maximum safety limit of {self.max_turns} turns. Resource released.")]
            )
        return None
