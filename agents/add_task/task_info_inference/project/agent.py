import json
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types
from pydantic import BaseModel, Field
from agents.tools import notion

class ProjectSuggestion(BaseModel):
    """项目推荐结果"""
    suggested_project: str | None = Field(description="推荐的项目名称,如果无法推断则为None")
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    reason: str = Field(description="推荐理由")

def load_notion_projects(callback_context: CallbackContext) -> types.Content | None:
    """Pre-fetch available projects from Notion and inject into session state.
    
    Returns:
        types.Content: If an error occurs, returns content to interrupt the agent.
        None: If successful, continues agent execution.
    """
    
    # 1. Fetch from Notion
    projects_json_str = notion.query_database(query="Project")
    
    available_projects = []
    try:
        projects_data = json.loads(projects_json_str)
        if isinstance(projects_data, list):
            available_projects = [
                p.get("title", "Unknown Project") 
                for p in projects_data 
                if p.get("title")
            ]
        elif isinstance(projects_data, dict) and "error" in projects_data:
             error_msg = f"Failed to load projects from Notion: {projects_data['error']}"
             print(f"[ProjectSuggester] {error_msg}")
             # Interrupt the flow by returning Content
             return types.Content(parts=[types.Part(text=error_msg)])
             
    except json.JSONDecodeError:
        error_msg = f"Invalid JSON response from Notion tool: {projects_json_str}"
        print(f"[ProjectSuggester] {error_msg}")
        # Interrupt the flow by returning Content
        return types.Content(parts=[types.Part(text=error_msg)])
        
    # 2. Inject into Session State
    callback_context.state["available_projects"] = ", ".join(available_projects) if available_projects else "None"
    
    # Return None to continue execution
    return None


def ProjectSuggester(name: str = "ProjectSuggester") -> LlmAgent:
    """
    ProjectSuggester Agent - 推断任务所属项目
    
    职责:
    - 基于任务内容推断可能的项目归属
    - 提供置信度和推荐理由
    
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="推断任务所属项目的Agent",
        instruction="""
你是一个项目推断助手。根据任务信息推断任务可能属于哪个项目。

任务信息在session state的"basic_info"字段中。
缺失字段信息在"scan_result"字段中。

当前可用的项目列表 (来自 Notion):
[{available_projects}]

你的任务:
1. 分析任务的标题和内容
2. 如果"project"在缺失字段列表中,尝试推断任务可能属于的项目
3. 从"当前可用的项目列表"中选择最匹配的一个。如果不匹配任何现有项目，且任务意图明确需要新项目，可以建议新项目名。
4. 给出推荐的项目名称、置信度(0.0-1.0)和推荐理由

如果无法推断项目,将suggested_project设为null,confidence设为0.0。

请以JSON格式输出结果,包含:
- suggested_project: 推荐的项目名称或null  
- confidence: 置信度(0.0到1.0之间的浮点数)
- reason: 推荐理由的文字说明
""",
        output_schema=ProjectSuggestion,
        output_key="project_suggestion",
        before_agent_callback=load_notion_projects
    )

