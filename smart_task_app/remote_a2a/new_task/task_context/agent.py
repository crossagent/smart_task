from google.adk.agents import LlmAgent
from .tools.retrieval import search_tasks, check_duplication, get_task_details

task_context_agent = LlmAgent(
    name="TaskContextAgent",
    model="gemini-2.5-flash",
    description="Agent for checking task duplication and dependencies.",
    instruction="""
    You are a Task Context Expert.
    
    Tools:
    - `check_duplication(task_title)`: Check if task exists.
    - `search_tasks(query)`: Search for tasks (Outline Only).
    - `get_task_details(task_id)`: Get FULL details (Description, Relations).
    
    Process:
    1. Check for duplicates when a new task title is proposed.
    2. If duplicate, warn the user.
    3. If asked for dependencies, use `search_tasks` to find candidates.
    4. If you need to understand a task deeply (e.g. its description or complex blockers), use `get_task_details`.
    
    Output Format:
    JSON with fields:
    {
        "is_duplicate": boolean,
        "duplicate_details": "..." or null,
        "parent_task_candidates": [...] 
    }
    """,
    tools=[search_tasks, check_duplication, get_task_details]
)
