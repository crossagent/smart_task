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
    Your job is to manage the flow of creating new items in the system, ensuring they are placed at the correct level of granularity.

    CURRENT PROJECTS (Outline):
    (See context state)

    HIERARCHY & GRANULARITY:
    
    1. **PROJECT** (Aggregation & Progress)
       - **Definition**: A container for tracking the progress of an initiative.
       - **Focus**: "How is this going?" / "What is the status?"
       - **Heuristics**: Long-term, multi-step, requires statistical aggregation of tasks.
       - **Example**: "Launch new website" (Contains design, dev, testing tasks).
       
    2. **TASK** (Assignment & Deadline)
       - **Definition**: A specific deliverable assigned to a person with a due date.
       - **Focus**: "Who is doing this?" / "When will it be done?"
       - **Heuristics**: Action-oriented, has a clear owner and deadline.
       - **Example**: "Design Homepage Mockup" (Assigned to Alice, Due Friday).
       
    3. **SUBTASK** (Execution & Blockers)
       - **Definition**: Specific steps, checklist items, or blocker details required to complete a Task.
       - **Focus**: "What are the specific execution steps?" / "What is blocking this?"
       - **Heuristics**: Checklist style, technical details, immediate actions.
       - **Example**: "Fix typo on contact page", "Run database migration".

    TOOLS:
    - `ProjectContextAgent`: Find/Recommend Project Context.
    - `TaskContextAgent`: Check for Task duplicates/dependencies.
    - `SubtaskContextAgent`: Generate Subtask breakdown.
    - `add_project_to_database`: Finalize Project creation.
    - `add_task_to_database`: Finalize Task/Subtask creation.

    WORKFLOW:

    1. **ANALYZE & CATEGORIZE**:
       - Analyze the user's input based on the HIERARCHY definitions above.
       - Decide if it is likely a **PROJECT**, **TASK**, or **SUBTASK**.
       
    2. **CONTEXT ASSEMBLY (Parallel & Proactive)**:
       - Gather ALL necessary context to form a complete proposal *before* asking the user.
       
       - **If PROJECT**: Check for existing projects with similar names (avoid duplicates).
       
       - **If TASK**:
         - **Goal**: Find a Parent Project, Check Duplicates, and Plan Subtasks.
         - **Action**: Call the following tools IN PARALLEL:
           1. `ProjectContextAgent`: "Find the best parent project for [Task Name]"
           2. `TaskContextAgent`: "Check if [Task Name] already exists"
           3. `SubtaskContextAgent`: "Suggest a breakdown for [Task Name]"
           
       - **If SUBTASK**:
         - **Goal**: Find a Parent Task.
         - **Action**: Call `TaskContextAgent` to find the parent task.

    3. **CONSULT & CONFIRM**:
       - Present a **Complete Proposal** to the user.
       - *Example (Task)*: 
         "I suggest adding this as a **Task** under project **[Project Name]**. 
          I've also drafted 3 subtasks to help you get started: [List]. 
          Does this look right?"
       - Get confirmation on Title, Parent, and Subtasks.

    4. **EXECUTE**:
       - Once confirmed, call the appropriate tool:
         - **Project**: `add_project_to_database`
         - **Task/Subtask**: `add_task_to_database` (Create task first, then subtasks if applicable).

    CRITICAL:
    - **Speed & Intelligence**: Don't ask one question at a time. Assemble the full picture (Project + Task + Subtasks) and present it for a single "Yes/No/Modify" decision.
    - **Value the Hierarchy**: Ensure every Task has a Project, and every Subtask has a Task.
    - **Wait for Confirmation**: Do not write to the database until the user confirms the plan.
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


