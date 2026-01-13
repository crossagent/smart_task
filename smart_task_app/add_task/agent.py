from typing import AsyncGenerator, List, Dict, Any, Optional

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import InvocationContext, ToolContext
from google.adk.events import Event
from google.genai import types

# Import Skills (Sub-Agents)
from .granularity.agent import GranularityAdvisor
from .scanner import SchemaScanner
from .task_info_inference import InferenceOrchestrator as InfoInferenceOrchestrator
from .clarification import ClarificationSynthesizer
from .fulfillment import Fulfillment


from typing import AsyncGenerator, List, Dict, Any, Optional

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext, ToolContext
from google.adk.events import Event
from google.adk.tools import AgentTool  # Native Import
from google.genai import types

# Import Skills (Sub-Agents)
from .granularity.agent import GranularityAdvisor
from .scanner import SchemaScanner
from .task_info_inference import InferenceOrchestrator as InfoInferenceOrchestrator
from .clarification import ClarificationSynthesizer
from .fulfillment import Fulfillment


# --- Artifact Tools (Standalone Functions) ---

def read_task_artifact(context: ToolContext) -> str:
    """Reads the content of the 'task.md' artifact."""
    content = context.session.state.get("task_md_content", "")
    return content if content else "(Artifact is empty)"

def update_task_artifact(context: ToolContext, content: str) -> str:
    """Updates (overwrites) the 'task.md' artifact with new markdown content."""
    context.session.state["task_md_content"] = content
    try:
        # Simulate saving to ADK Artifacts
        pass 
    except Exception:
        pass
    return "Artifact 'task.md' updated successfully."


def AddTaskWorkflow(name: str = "AddTaskWorkflow") -> BaseAgent:
    """
    AddTaskWorkflow - Root Agent (LlmAgent)
    
    Architecture:
    - Root: LlmAgent (The Manager)
    - Tools: 
      1. Artifact Tools (read/update plan)
      2. Sub-Agents (wrapped as Native AgentTools)
    """
    
    # 1. Instantiate Sub-Agents (Skills)
    advisor = GranularityAdvisor()
    scanner = SchemaScanner()
    inference = InfoInferenceOrchestrator()
    clarifier = ClarificationSynthesizer()
    fulfillment = Fulfillment()
    
    # 2. Wrap them as Tools using Native ADK Wrapper
    # The Root LLM will see these as tools: 'run_granularityadvisor', 'run_schemascanner', etc.
    skill_tools = [
        AgentTool(advisor),
        AgentTool(scanner),
        AgentTool(inference),
        AgentTool(clarifier),
        AgentTool(fulfillment)
    ]
    
    # 3. Create Root Agent
    return LlmAgent(
        name=name,
        system_prompt=(
            "You are an autonomous workflow manager for creating tasks/projects.\n"
            "Your Single Source of Truth is the `task.md` artifact. "
            "You must maintain a checklist in `task.md` to track progress.\n\n"
            "**Workflow**:\n"
            "1. ALWAYS read the `task.md` artifact first (`read_task_artifact`).\n"
            "2. If `task.md` is empty, initialize it with a default plan using `update_task_artifact`.\n"
            "   Default Plan:\n"
            "   - [ ] Analyze Input (Granularity)\n"
            "   - [ ] Scan for Missing Fields\n"
            "   - [ ] Infer Missing Info\n"
            "   - [ ] Fulfillment\n"
            "3. Look for the next unchecked item `[ ]`.\n"
            "4. Call the corresponding Agent Tool (e.g., `run_granularityadvisor`).\n"
            "5. After the agent returns success, update `task.md` to mark it as `[x]`.\n"
            "6. If an agent reports ambiguity/issues (e.g., Granularity is AMBIGUOUS), insert a clarification step `[ ] Ask User` into `task.md` and ASK the user.\n"
            "7. Repeat until all items are `[x]`.\n\n"
            "**Constraint**:\n"
            " - Do not make up information. Use the tools.\n"
            " - If you need to ask the user, just output the question as your final response."
        ),
        tools=[
            read_task_artifact,
            update_task_artifact,
            *skill_tools
        ]
    )


add_task_agent = AddTaskWorkflow()
