from google.adk.agents import LlmAgent
from .tools.breakdown import suggest_breakdown

subtask_context_agent = LlmAgent(
    name="SubtaskContextAgent",
    model="gemini-2.5-flash",
    description="Agent for breaking down tasks into subtasks.",
    instruction="""
    You are a Subtask Planning Expert.
    Your goal is to break down a Task into actionable Subtasks (Action Items).
    
    Tools:
    - `suggest_breakdown`: (Placeholder)
    
    Process:
    1. Receive a Task Title/Description.
    2. Generate a list of 3-5 concrete Subtasks.
    3. Be specific and actionable.
    
    Output Format:
    JSON:
    {
        "subtasks": ["Action 1", "Action 2", ...]
    }
    """,
    tools=[suggest_breakdown] # Even if redundant, good for structure
)
