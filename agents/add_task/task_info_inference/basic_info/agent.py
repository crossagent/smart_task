from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class BasicInfoResult(BaseModel):
    """基本信息提取结果"""
    title: str = Field(description="任务标题")
    type: str = Field(description="任务类型: task 或 meeting")


def BasicInfoInference(name: str = "BasicInfoInference") -> LlmAgent:
    """
    BasicInfoInference Agent - 提取任务标题和类型
    
    职责:
    - 从用户输入中提取任务标题
    - 识别任务类型(task/meeting)
    
    输出: 自动保存到 session.state["basic_info"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="提取任务基本信息的Agent",
        instruction="""
你是一个任务信息提取助手。从用户输入中提取任务的基本信息。

任务:
1. 从用户输入中提取任务标题 (user_input 在 session state 中)
2. 判断任务类型:
   - 如果输入中提到"meeting"、"会议"等关键词,type设为"meeting"
   - 否则type设为"task"

请以JSON格式输出结果,包含以下字段:
- title: 任务标题
- type: 任务类型("task" 或 "meeting")
""",
        output_schema=BasicInfoResult,
        output_key="basic_info"  # 并行推断时，各Agent写入不同的key通常更安全，但这里设计为 SchemaScanner 读取 basic_info。
                                 # 如果 InferenceOrchestrator 是并行运行，多个 Agent 写入 session state 可能是分开的 keys。
                                 # ADK 的 ParallelAgent 会收集所有 sub-agents 的输出。
                                 # 根据 Architecture Plan, 我们希望它最终合并进 basic_info。
                                 # 这里暂时直接写入 basic_info，因为它是唯一的 writer of 'title'.
    )
