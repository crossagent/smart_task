from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class DueDateSuggestion(BaseModel):
    """截止日期推荐结果"""
    suggested_due_date: str | None = Field(description="推荐的截止日期(YYYY-MM-DD格式),如果无法推断则为None")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="推荐理由")


def DueDateEstimator(name: str = "DueDateEstimator") -> LlmAgent:
    """
    DueDateEstimator Agent - 推断任务截止日期
    
    职责:
    - 从任务描述中提取或推断截止日期
    - 理解相对时间表达(如"明天"、"下周")
    
    输出: 自动保存到 session.state["due_date_suggestion"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="推断任务截止日期的Agent",
        instruction="""
你是一个日期推断助手。根据任务信息推断任务的截止日期。

任务信息在session state的"basic_info"字段中。
缺失字段信息在"scan_result"字段中。

你的任务:
1. 分析任务标题和内容中的时间信息
2. 如果"due_date"在缺失字段列表中,尝试推断截止日期
3. 理解相对时间表达:
   - "明天" -> 当前日期+1天
   - "下周" -> 当前日期+7天
   - "本周五" -> 本周的周五
4. 给出推荐的截止日期(YYYY-MM-DD格式)、置信度和理由

当前日期参考: 2025-11-19

如果无法推断日期,将suggested_due_date设为null,confidence设为0.0。

请以JSON格式输出结果,包含:
- suggested_due_date: 推荐的截止日期(格式:YYYY-MM-DD)或null
- confidence: 置信度(0.0到1.0之间的浮点数)
- reason: 推荐理由的文字说明
""",
        output_schema=DueDateSuggestion,
        output_key="due_date_suggestion"
    )

