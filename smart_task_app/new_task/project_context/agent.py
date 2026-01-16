from google.adk.agents import LlmAgent
from .tools.retrieval import search_projects, get_project_context

project_context_agent = LlmAgent(
    name="ProjectContextAgent",
    model="gemini-2.5-flash",
    description="Agent for retrieving Project context and goals.",
    instruction="""
    You are a Project Context Expert.
    Your goal is to help find the right Parent Project for a task.
    
    Tools:
    - `search_projects(query)`: Search for a project by name.
    
    Process:
    1. Receive a task description or project name hint.
    2. Search for existing projects.
    3. Return the most relevant Project ID and Name.
    4. If no project is found, strictly reply "NO_PROJECT_FOUND".
    
    Output Format:
    JSON with fields:
    {
        "project_id": "...",
        "project_name": "...",
        "reasoning": "..."
    }
    """,
    tools=[search_projects, get_project_context]
)
