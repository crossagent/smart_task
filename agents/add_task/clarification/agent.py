from typing import Dict
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class ClarificationMessage(BaseModel):
    """澄清消息结果"""
    need_clarification: bool = Field(description="是否需要用户澄清")
    questions: list[str] = Field(description="需要询问的问题列表")
    suggestions: str = Field(description="推荐的值字典(JSON字符串)")


def ClarificationSynthesizer(name: str = "ClarificationSynthesizer") -> LlmAgent:
    """
    ClarificationSynthesizer Agent - 生成澄清问题
    
    职责:
    - 汇总所有推断结果
    - 生成友好的澄清问题
    - 决定是否需要用户澄清
    
    输出: 自动保存到 session.state["clarification"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="生成澄清问题的Agent",
        instruction="""
你是一个澄清问题生成助手。基于推断结果生成友好的澄清问题。

可用信息:
- 基本信息: {basic_info}
- 缺失字段: {scan_result}
- 项目推荐: {project_suggestion}
- 日期推荐: {due_date_suggestion}
- 优先级推荐: {priority_suggestion}

你的任务:
1. 检查所有必填字段是否已齐全或可以从推断结果中获取
2. 对于有高置信度(>0.7)推断的字段,可以直接使用,不需要澄清
3. 对于低置信度(<0.7)或无法推断的字段,生成友好的澄清问题

示例问题:
- "这个任务是属于 [推荐项目] 吗?"
- "截止日期是 [推荐日期] 吗?"
- "优先级设为 [推荐优先级] 可以吗?"

如果所有字段都已齐全或推断置信度都很高,设置 need_clarification=false。

请以JSON格式输出结果,包含:
- need_clarification: 是否需要用户澄清(true/false)
- questions: 问题列表(如果need_clarification为false则为空列表)
- suggestions: 推荐值的字典,格式如 {"project": "Personal", "due_date": "2025-11-20"}
""",
        output_schema=ClarificationMessage,
        output_key="clarification"
    )
