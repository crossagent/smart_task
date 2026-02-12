from typing import Optional
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import AgentTool
from google.genai import types

# Import Sub-Agents
from .project_context.agent import project_context_agent
from .task_context.agent import task_context_agent
from .subtask_context.agent import subtask_context_agent

# Import Notion Tools
from .tools.notion import add_task_to_database, add_project_to_database

# Import retrieval tool
from .project_context.tools.retrieval import get_project_outline

# Wrap Agents as Tools
project_agent_tool = AgentTool(project_context_agent)
task_agent_tool = AgentTool(task_context_agent)
subtask_agent_tool = AgentTool(subtask_context_agent)

def load_project_context(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Callback to load Project Outline into state before agent runs.
    """
    try:
        outline_str = get_project_outline()
        # Store in state
        callback_context.state["project_context"] = outline_str
        print(f"[Callback] Loaded Project Context: {len(outline_str)} chars")
    except Exception as e:
        print(f"[Callback] Failed to load project context: {e}")
        callback_context.state["project_context"] = "[]"
    return None

def orchestrator_instruction() -> str:
    """
    Dynamic instruction that includes Project Context from state.
    """
    return f"""
    You are the 'Add Task' Orchestrator.
    Your job is to manage the flow of creating new items in the system.
    
    CURRENT PROJECTS (Outline):
    (See context state)
    
    HIERARCHY:
    1. **Project** (Top level, Goal-oriented)
    2. **Task** (Belongs to a Project, Deliverable)
    3. **Subtask** (Belongs to a Task, Action Items)
    
    TOOLS:
    - `ProjectContextAgent`: Find/Recommend Project Context.
    - `TaskContextAgent`: Check for Task duplicates/dependencies.
    - `SubtaskContextAgent`: Generate Subtask breakdown.
    - `add_project_to_database`: Finalize Project creation.
    - `add_task_to_database`: Finalize Task/Subtask creation.
    
    WORKFLOW:
    
    1. **Analyze Input**: Determine if User wants to create a PROJECT or a TASK.
       - If unclear, ASK the user.
       
    2. **If PROJECT**:
       - Ask user for Title, Goal (Why), Due Date.
       - Confirm details.
       - Call `add_project_to_database`.
       
    3. **If TASK**:
       - **Step A (Context)**: You have the Project Outline above. 
         - If the user's intent matches an existing project, use its ID.
         - If ambiguous, ask the user or call `ProjectContextAgent` for help.
         - *Must* have a parent project.
       - **Step B (Duplication)**: Call `TaskContextAgent` to check if this task already exists.
       - **Step C (Breakdown)**: Call `SubtaskContextAgent` to get a suggestion for 3-5 subtasks.
       - **Step D (Confirm)**: Present the full plan to the user.
       - **Step E (Execution)**: Call `add_task_to_database`.
    
    CRITICAL:
    - Do not invent IDs. Use the tools.
    - Wait for User Confirmation before writing to Database.
    """

root_agent = LlmAgent(
    name="AddTaskOrchestrator",
    model="gemini-2.5-flash",
    description="Orchestrator for adding new Projects or Tasks.",
    instruction=orchestrator_instruction(),
    before_agent_callback=load_project_context,
    tools=[
        project_agent_tool,
        task_agent_tool,
        subtask_agent_tool,
        add_project_to_database,
        add_task_to_database
    ]
)


