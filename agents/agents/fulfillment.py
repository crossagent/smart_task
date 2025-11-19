from google.adk.agents import LlmAgent


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
    
    注意: ADK限制 - output_schema和tools不能同时使用,所以这里只用tools
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
   - 构建完整的task_data字典
   - 调用 write_task_to_db 工具创建任务
   - 告诉用户任务已成功创建
3. 如果 need_clarification 为 true:
   - 向用户输出 clarification.questions 中的问题
   - 不要调用工具

请用自然语言回复用户,告知结果或提出问题。
""",
        tools=[write_task_to_db]
        # 注意: 不能同时设置output_schema和tools,所以这里只用tools
    )


