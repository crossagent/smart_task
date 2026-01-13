from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field
from enum import Enum


class PriorityLevel(str, Enum):
    """优先级枚举"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PrioritySuggestion(BaseModel):
    """优先级推荐结果"""
    suggested_priority: PriorityLevel = Field(description="推荐的优先级: high/medium/low")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="推荐理由")


def PrioritySuggester(name: str = "PrioritySuggester") -> LlmAgent:
    """
    PrioritySuggester Agent - 推断任务优先级
    
    职责:
    - 基于任务内容和紧急程度推断优先级
    - 考虑关键词和上下文
    
    输出: 自动保存到 session.state["priority_suggestion"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="推断任务优先级的Agent",
        instruction="""
你是一个优先级推断助手。根据任务信息推断任务的优先级。

任务信息在session state的"basic_info"字段中。
缺失字段信息在"scan_result"字段中。

优先级分类:
- high: 高优先级 - 紧急重要的任务,如包含"紧急"、"ASAP"、"尽快"等关键词
- medium: 中优先级 - 正常任务,默认优先级
- low: 低优先级 - 不紧急的任务,如包含"有空"、"闲时"等关键词

你的任务:
1. 分析任务标题和内容
2. 如果"priority"在缺失字段列表中,推断任务优先级
3. 考虑以下因素:
   - 任务关键词(紧急、重要等)
   - 截止日期的紧迫性
   - 任务类型(会议通常优先级较高)
4. 给出推荐的优先级、置信度和理由

默认推荐"medium"优先级。

请以JSON格式输出结果,包含:
- suggested_priority: 推荐的优先级("high"、"medium"或"low")
- confidence: 置信度(0.0到1.0之间的浮点数)
- reason: 推荐理由的文字说明
""",
        output_schema=PrioritySuggestion,
        output_key="priority_suggestion"
    )

