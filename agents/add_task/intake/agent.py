from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class TaskBasicInfo(BaseModel):
    """从用户输入中提取的任务基本信息"""
    title: str = Field(description="任务标题")
    type: str = Field(description="任务类型: task 或 meeting")
    raw_input: str = Field(description="原始用户输入")


def IntakeRouter(name: str = "IntakeRouter") -> LlmAgent:
    """
    IntakeRouter Agent - 从用户输入中提取任务基本信息
    
    职责:
    - 解析用户输入
    - 识别任务类型(task/meeting)
    - 提取任务标题
    
    输出: 自动保存到 session.state["basic_info"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="提取任务基本信息的Agent",
        instruction="""
你是一个任务信息提取助手。从用户输入中提取任务的基本信息。

任务:
1. 从用户输入中提取任务标题
2. 判断任务类型:
   - 如果输入中提到"meeting"、"会议"等关键词,type设为"meeting"
   - 否则type设为"task"
3. 保留原始输入

用户输入在session state中的"user_input"字段中。

请以JSON格式输出结果,包含以下字段:
- title: 任务标题
- type: 任务类型("task" 或 "meeting")
- raw_input: 原始用户输入
""",
        output_schema=TaskBasicInfo,
        output_key="basic_info"  # 自动保存到 session.state["basic_info"]
    )
