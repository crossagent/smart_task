from __future__ import annotations
import os
from google.adk.agents import LlmAgent
from google.adk.apps import App
from smart_task_app.shared_libraries.constants import MODEL

def write_smoke_signal(content: str) -> str:
    """Writes a message to smoke_signal.txt to verify A2A is working."""
    file_path = "smoke_signal.txt"
    with open(file_path, "w") as f:
        f.write(content)
    return f"Successfully wrote to smoke_signal.txt: {content}"

root_agent = LlmAgent(
    name="smoke_test",
    model=MODEL,
    description="Smoke Test Agent: 用于验证 A2A 协议连通性",
    instruction="""You are a Smoke Test Agent. 
Your only task is to listen for a message and use the write_smoke_signal tool to save it into a file.
This confirms that the A2A communication pipeline is functional.
""",
    tools=[write_smoke_signal]
)

app = App(
    name="smoke_test_app",
    root_agent=root_agent
)
