from google.adk.agents import LlmAgent
from google.adk.tools import AgentTool

# Import Sub-Agents
from .project_context.agent import project_context_agent
from .task_context.agent import task_context_agent
from .subtask_context.agent import subtask_context_agent

# Import Notion Tools
from .tools.notion import add_task_to_database, add_project_to_database

# Wrap Agents as Tools
project_agent_tool = AgentTool(project_context_agent)
task_agent_tool = AgentTool(task_context_agent)
subtask_agent_tool = AgentTool(subtask_context_agent)

new_task_agent = LlmAgent(
    name="AddTaskOrchestrator",
    model="gemini-2.5-flash",
    description="Orchestrator for adding new Projects or Tasks.",
    instruction="""
    You are the 'Add Task' Orchestrator.
    Your job is to manage the flow of creating new items in the system.
    
    HIERARCHY:
    1. **Project** (Top level, Goal-oriented)
    2. **Task** (Belongs to a Project, Deliverable)
    3. **Subtask** (Belongs to a Task, Action Items)
    
    TOOLS:
    - `run_projectcontextagent`: Find/Recommend Project Context.
    - `run_taskcontextagent`: Check for Task duplicates/dependencies.
    - `run_subtaskcontextagent`: Generate Subtask breakdown.
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
       - **Step A (Context)**: Call `run_projectcontextagent` to find the Parent Project.
         - *Must* have a parent project. If None found, ask user to select one or create one.
       - **Step B (Duplication)**: Call `run_taskcontextagent` to check if this task already exists.
       - **Step C (Breakdown)**: Call `run_subtaskcontextagent` to get a suggestion for 3-5 subtasks.
       - **Step D (Confirm)**: Present the full plan to the user:
         - Task Title
         - Parent Project
         - Subtasks (list)
         - Priority/Due Date
       - **Step E (Execution)**: 
         - Upon 'CONFIRM':
         - Call `add_task_to_database` for the main Task (returns ID).
         - Call `add_task_to_database` for each Subtask, passing `parent_task_id`.
    
    CRITICAL:
    - Do not invent IDs. Use the tools.
    - Wait for User Confirmation before writing to Database.
    """,
    tools=[
        project_agent_tool,
        task_agent_tool,
        subtask_agent_tool,
        add_project_to_database,
        add_task_to_database
    ]
)
