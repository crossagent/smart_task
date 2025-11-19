from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class FulfillmentResult(BaseModel):
    """任务完成结果"""
    success: bool = Field(description="是否成功创建任务")
    task_id: str | None = Field(description="创建的任务ID,如果失败则为None")
    message: str = Field(description="结果消息")


def write_task_to_db(task_data: dict) -> str:
    """
    将任务写入数据库的工具函数
    
    Args:
        task_data: 任务数据字典,包含title, project, due_date, priority等字段
    
    Returns:
        创建的任务ID或错误消息
    """
    # TODO: 实际的数据库操作
    # 这里是模拟实现
    print(f"[DB] Writing task to database: {task_data}")
    task_id = f"task_{hash(str(task_data)) % 10000}"
    return task_id


def Fulfillment(name: str = "Fulfillment") -> LlmAgent:
    """
    Fulfillment Agent - 完成任务创建
    
    职责:
    - 决定是否可以完成任务创建
    - 调用工具将任务写入数据库
    - 或者向用户输出澄清问题
    
    输出: 自动保存到 session.state["fulfillment_result"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="完成任务创建的Agent",
        instruction="""
你是一个任务创建完成助手。根据澄清结果决定是否可以创建任务。

可用信息:
- 基本信息: {basic_info}
- 扫描结果: {scan_result}
- 澄清结果: {clarification}
- 推断结果: {project_suggestion}, {due_date_suggestion}, {priority_suggestion}

你的任务:
1. 检查 {clarification} 中的 need_clarification 字段
2. 如果 need_clarification 为 false:
   - 汇总所有已有字段和推断的高置信度字段
   - 调用 write_task_to_db 工具创建任务
   - 设置 success=true 和返回的 task_id
3. 如果 need_clarification 为 true:
   - 向用户输出 clarification.questions 中的问题
   - 设置 success=false, task_id=null
   - message 包含需要澄清的问题

请以JSON格式输出结果,包含:
- success: 是否成功创建任务
- task_id: 任务ID(如果成功)或null
- message: 结果消息或澄清问题
""",
        tools=[write_task_to_db],
        output_schema=FulfillmentResult,
        output_key="fulfillment_result"
    )

