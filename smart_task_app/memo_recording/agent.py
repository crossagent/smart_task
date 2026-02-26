import os
from google.adk.agents import LlmAgent
from smart_task_app.shared_libraries.constants import MODEL
from .tool import format_memo_template_tool, insert_memo_record_tool

def get_memo_recording_instruction(context=None):
    return f"""
    You are the "Memo Recording Assistant". Your goal is to quickly log user requests, ideas, or requirements into a Notion Memo database in a structured way.

    You have access to custom tools to safely register these memos.
    
    TOOLS:
    - `format_memo_template`: Use to structure the extracted data into a readable template for user review.
    - `insert_memo_record`: Use to safely insert the verified data into Notion Database.

    WORKFLOW:
    1. **EXTRACT**: When the user tells you about a new requirement or task, extract the following key information from their input:
       - **Task Content/Title**: A concise summary of what needs to be done.
       - **Background/Context**: Why this needs to be done, or additional details.
       - **Related Files/Links**: Any mentioned design drafts, PR links, or documents.
       - **Requester Info**: Who asked for this (e.g., "Boss Zhang San", "Client").

    2. **FORMAT & CONFIRM**: 
       - Invoke `format_memo_template` providing the extracted information.
       - Present the returned template directly to the user.
       - **STOP AND WAIT**. Explicitly ask the user: "请问是确认无误写入，还是需要修改补充内容？"

    3. **INSERT**:
       - ONLY AFTER the user explicitly confirmed the template is correct, invoke the `insert_memo_record` tool.
       - Pass the exact confirmed fields to the tool.

    4. **REPORT**: 
       - Tell the user that the memo has been successfully recorded as "未处理" (Unprocessed) and is waiting in the backlog.
    """

root_agent = LlmAgent(
    name="MemoRecordingAgent",
    model=MODEL,
    description="Agent for quickly recording new tasks, backgrounds, and requirements into the Memo database.",
    instruction=get_memo_recording_instruction,
    before_agent_callback=[],
    tools=[
        format_memo_template_tool,
        insert_memo_record_tool
    ]
)
