from enum import Enum
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class GranularityDecision(str, Enum):
    """颗粒度决策枚举"""
    PROJECT = "PROJECT"
    TASK = "TASK"
    SUBTASK = "SUBTASK"
    AMBIGUOUS = "AMBIGUOUS"


class GranularityResult(BaseModel):
    """颗粒度分析结果"""
    title: str = Field(description="从用户输入中提取的任务标题")
    type: str = Field(description="任务类型: task 或 meeting")
    decision: GranularityDecision = Field(description="决策结果: PROJECT/TASK/SUBTASK/AMBIGUOUS")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="判断理由")
    clarification_question: str | None = Field(description="如果决策是AMBIGUOUS，提供澄清问题。否则为None。")


def GranularityAdvisor(name: str = "GranularityAdvisor") -> LlmAgent:
    """
    GranularityAdvisor Agent - 意图识别与颗粒度分析 (Unified Intake)
    
    职责:
    - 提取基础信息 (Title, Type)
    - 分析任务颗粒度 (Project/Task/Subtask)
    - 识别模糊意图
    
    输出: 自动保存到 session.state["granularity_result"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="分析任务意图和颗粒度的Agent",
        instruction="""
你是一个任务智能分析助手。请从用户输入中提取关键信息并分析任务层级。

输入信息:
- user_input: 用户原始输入 (在 session state 中)

你的工作包含两部分:

第一部分: 基础信息提取 (Intake)
1. **Title**: 提取清晰的任务标题。
2. **Type**: 识别是 task 还是 meeting (包含"会议"等词)。

第二部分: 颗粒度分析 (Granularity Analysis)
判断标准 (以交付物和责任人视角):
1. **PROJECT (项目)**: 目标导向，多交付物，需要协作。"重构", "上线", "方案落地"。
2. **TASK (任务)**: 交付物导向，单人负责。"修复", "撰写", "开发"。
3. **SUBTASK (子任务)**: 动作导向，执行步骤。"申请权限", "联系某人"。
4. **AMBIGUOUS (模糊)**: 无法确定交付物范围。"方案", "处理X问题"。

输出要求:
- 给出 Title 和 Type。
- 给出 Decision (PROJECT/TASK/SUBTASK/AMBIGUOUS)。
- 给出 Confidence (0.0-1.0)。
- 给出 Reason。
- **如果决策是 AMBIGUOUS**，必须给出一个友好的澄清问题。

请以JSON格式输出。
""",
        output_schema=GranularityResult,
        output_key="granularity_result"
    )
