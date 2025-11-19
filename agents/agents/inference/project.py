from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class ProjectSuggestion(BaseModel):
    """项目推荐结果"""
    suggested_project: str | None = Field(description="推荐的项目名称,如果无法推断则为None")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="推荐理由")


def ProjectSuggester(name: str = "ProjectSuggester") -> LlmAgent:
    """
    ProjectSuggester Agent - 推断任务所属项目
    
    职责:
    - 基于任务内容推断可能的项目归属
    - 提供置信度和推荐理由
    
    输出: 自动保存到 session.state["project_suggestion"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="推断任务所属项目的Agent",
        instruction="""
你是一个项目推断助手。根据任务信息推断任务可能属于哪个项目。

任务信息在session state的"basic_info"字段中。
缺失字段信息在"scan_result"字段中。

你的任务:
1. 分析任务的标题和内容
2. 如果"project"在缺失字段列表中,尝试推断任务可能属于的项目
3. 给出推荐的项目名称、置信度(0.0-1.0)和推荐理由

如果无法推断项目,将suggested_project设为null,confidence设为0.0。

请以JSON格式输出结果,包含:
- suggested_project: 推荐的项目名称或null  
- confidence: 置信度(0.0到1.0之间的浮点数)
- reason: 推荐理由的文字说明
""",
        output_schema=ProjectSuggestion,
        output_key="project_suggestion"
    )

