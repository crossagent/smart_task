from typing import Dict
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class MissingFieldsResult(BaseModel):
    """Schema扫描结果"""
    parsed_fields: str = Field(description="已解析的字段字典(JSON字符串)")
    missing_fields: list[str] = Field(description="缺失的必填字段列表")
    all_fields_present: bool = Field(description="是否所有必填字段都已齐全")


def SchemaScanner(name: str = "SchemaScanner") -> LlmAgent:
    """
    SchemaScanner Agent - 对比schema找出缺失字段
    
    职责:
    - 检查必填字段是否齐全
    - 识别缺失的字段
    - 判断是否需要进一步推断或澄清
    
    输出: 自动保存到 session.state["scan_result"]
    """
    return LlmAgent(
        name=name,
        model="gemini-2.0-flash",
        description="扫描并识别缺失字段的Agent",
        instruction="""
你是一个任务schema扫描助手。根据任务schema检查缺失字段。

必填字段清单:
- title: 任务标题
- project: 所属项目
- due_date: 截止日期
- priority: 优先级

任务信息在session state的"basic_info"字段中。

你的任务:
1. 检查已有哪些字段(从basic_info中获取)
2. 对比必填字段清单,找出缺失的字段
3. 判断是否所有必填字段都已齐全

请以JSON格式输出结果,包含:
- parsed_fields: 当前已有的字段字典
- missing_fields: 缺失的必填字段列表
- all_fields_present: 如果所有必填字段都存在为true,否则为false
""",
        output_schema=MissingFieldsResult,
        output_key="scan_result"  # 自动保存到 session.state["scan_result"]
    )
