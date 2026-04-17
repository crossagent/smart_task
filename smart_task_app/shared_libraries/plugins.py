import logging
import httpx
import os
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from .agent_utils import sync_agent_workspace, dispatch_agent_deliverables

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

    async def before_model_callback(self, *, callback_context: CallbackContext, llm_request: LlmRequest) -> LlmResponse | None:
        # Check current turn count in this invocation
        # We count events that are from the model (llm_response) in this invocation
        invocation_context = callback_context.invocation_context
        invocation_id = invocation_context.invocation_id
        session = invocation_context.session
        
        # Identify how many successful model responses we've had in THIS invocation
        model_turns = [e for e in session.events if e.invocation_id == invocation_id and e.author == 'model']
        
        if len(model_turns) >= self.max_turns:
            task_id = session.id
            logger.warning(f"Safety Triggered: Task {task_id} reached max model turns ({self.max_turns}).")
            
            # Proactively notify Hub to mark task as blocked
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        f"{HUB_URL}/api/task/{task_id}/block", 
                        params={"reason": f"MaxTurnsPlugin triggered ({self.max_turns} model turns exceeded)"}
                    )
            except Exception as e:
                logger.error(f"Failed to notify Hub of blocked task {task_id}: {e}")

            # Return a short-circuiting response
            return LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"ERROR: Execution terminated by MaxTurnsPlugin. Reached maximum safety limit of {self.max_turns} model turns.")]
                ),
                finish_reason=types.FinishReason.STOP
            )
        return None

class GitSyncPlugin(BasePlugin):
    """
    Automates Git synchronization for distributed agents.
    Full isolation: Pull before run, Push after run.
    """
    def __init__(self):
        super().__init__(name="git_sync")

    async def before_run_callback(self, *, invocation_context: InvocationContext) -> types.Content | None:
        logger.info("GitSyncPlugin: Performing pre-run synchronization...")
        result = sync_agent_workspace()
        if "failed" in result.lower():
            logger.error(f"GitSyncPlugin: Pre-run sync failed: {result}")
            # We don't necessarily want to block the run if it's just a pull issue, 
            # but we log it. In a strict environment, we could return an error Content here.
        return None

    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        logger.info("GitSyncPlugin: Performing post-run delivery...")
        # Use session ID or a summary for the commit message
        session_id = invocation_context.session.id
        msg = f"Task {session_id} update from {invocation_context.root_agent.name}"
        result = dispatch_agent_deliverables(commit_message=msg)
        if "failed" in result.lower():
            logger.error(f"GitSyncPlugin: Post-run delivery failed: {result}")
        else:
            logger.info(f"GitSyncPlugin: Post-run delivery successful: {result}")

