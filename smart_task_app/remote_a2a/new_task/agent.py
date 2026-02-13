from typing import Optional
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import AgentTool
from google.genai import types
from google.adk.agents.readonly_context import ReadonlyContext
from smart_task_app.shared_libraries.constants import MODEL

# Import retrieval tools (consolidated into tools/retrieval.py)
from .tools.retrieval import get_project_outline, search_projects, search_tasks

# Import Notion Tools
from .tools.notion import add_task_to_database, add_project_to_database, update_task, update_project

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

def orchestrator_instruction(context: ReadonlyContext = None) -> str:
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
    - `search_projects(query)`: Search for existing projects.
    - `search_tasks(query, project_id)`: Search for existing tasks. **MUST** provide `project_id` to scope search.
    - `add_project_to_database`: Create a NEW Project.
    - `update_project`: Update an EXISTING Project.
    - `add_task_to_database`: Create a NEW Task/Subtask.
    - `update_task`: Update an EXISTING Task/Subtask.

    WORKFLOW - CONTEXT ASSEMBLY (Search -> Check -> Upsert):

    1. **ANALYZE**: Determine if the user input is a **PROJECT**, **TASK**, or **SUBTASK**.

    2. **ASSEMBLE & CHECK**:
       
       - **If PROJECT**:
         1. Call `search_projects` with the name.
         2. **Logic**:
            - **Found Match?** -> Plan to **UPDATE** the existing project (using `update_project`).
            - **No Match?** -> Plan to **CREATE** a new project (using `add_project_to_database`).
       
       - **If TASK**:
         1. Call `search_projects` to find the Parent Project ID. **CRITICAL**: You must have a Project ID.
         2. Call `search_tasks(query, project_id=...)` using the ID found in step 1.
         3. **Logic**:
            - **Found Match?** -> Plan to **UPDATE** the existing task (using `update_task`).
            - **No Match?** -> Plan to **CREATE** a new task (using `add_task_to_database`).
            - *Internal Step*: Generate 3-5 subtasks to help the user.
            
       - **If SUBTASK**:
         1. Call `search_tasks` (with project_id if known, or scope it) to find the Parent Task.
         2. Check if this subtask text appears in the parent task's children/subtasks (if visible) or generic search.
         3. **Logic**:
            - **Found Match?** -> Plan to **UPDATE** (using `update_task`).
            - **No Match?** -> Plan to **CREATE** (using `add_task_to_database` linked to parent).

    3. **CONSULT**:
       - Present the **Complete Proposal** to the user.
       - *Example (Update)*: "I found an existing task 'Buy Milk'. Do you want me to update its status or due date?"
       - *Example (Create)*: "I suggest creating a new Task 'Buy Milk' under Project 'Life'. I've also drafted subtasks..."
       - Get confirmation.

    4. **EXECUTE**:
       - Once confirmed, call the specific tool decided in Step 2 (Add or Update).

    CRITICAL:
    - **Scoped Search**: NEVER search for tasks without a Project ID context if possible.
    - **Upsert Logic**: Always prefer updating an existing item over creating a duplicate.
    - **Value the Hierarchy**: Ensure every Task has a Project, and every Subtask has a Task.
    - **Wait for Confirmation**: Do not write/update DB until confirmed.
    """

root_agent = LlmAgent(
    name="AddTaskOrchestrator",
    model=MODEL,
    description="Orchestrator for adding new Projects or Tasks.",
    instruction=orchestrator_instruction,
    before_agent_callback=load_project_context,
    tools=[
        search_projects,
        search_tasks,
        add_project_to_database,
        update_project,
        add_task_to_database,
        update_task
    ]
)


