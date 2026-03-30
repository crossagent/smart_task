from __future__ import annotations

import json
import os

from google.adk.tools import FunctionTool, ToolContext

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db_id(env_var: str, default_val: str) -> str:
    return os.environ.get(env_var, default_val)

def _get_graph_name() -> str:
    return _get_db_id("LOGSEQ_GRAPH_NAME", "default")


async def _call_logseq_tool(tool_name: str, args: dict, tool_context: ToolContext):
    """Call a Logseq MCP tool by name and return the parsed JSON response."""
    from smart_task_app.shared_libraries.logseq_util import get_logseq_mcp_tool  # pylint: disable=import-outside-toplevel

    toolset = get_logseq_mcp_tool()
    tools = await toolset.get_tools()
    target = next((t for t in tools if t.name == tool_name), None)
    if target is None:
        raise ValueError(f"Logseq MCP tool '{tool_name}' not found.")
    raw = await target.run_async(args=args, tool_context=tool_context)

    # Normalise response to a dictionary
    if isinstance(raw, str):
        return json.loads(raw)
    if isinstance(raw, dict) and "content" in raw:
        content_text = raw["content"][0].get("text", "{}")
        return json.loads(content_text)
    if hasattr(raw, "content"):
        return json.loads(raw.content[0].text)

    return raw

async def query_logseq_metadata(
    metadata_type: str,
    tool_context: ToolContext = None
) -> str:
    """查询具体的元数级实体（module, resource, feature, initiative）内容。
    
    使用该工具来获取目前系统中有哪些存在的 Module，Resource，Feature 或 Initiative 及其对应的 块/页面 ID。
    
    Args:
      metadata_type: 必须是 'module', 'resource', 'feature' 或 'initiative' 中的一个。
    """
    valid_types = ["module", "resource", "feature", "initiative"]
    if metadata_type.lower() not in valid_types:
        return f"Error: 无法识别的元数据类型 '{metadata_type}'。请选择 'module', 'resource', 'feature' 或 'initiative'。"
        
    class_name = metadata_type.capitalize()
    
    try:
        # 2026 Logseq DB 模式下，我们通过属性搜索对应的 Class
        # 假设使用的工具是 search
        data = await _call_logseq_tool(
            "search",
            {"query": f"class:: [[{class_name}]]"},
            tool_context
        )
        results = data.get("results", [])
        if not results:
            return f"没有找到任何 {class_name} 数据。"
            
        lines = [f"=== 当前系统中的 {class_name} 列表 ==="]
        for item in results:
            item_id = item.get("uuid", item.get("id", ""))
            name = item.get("content", "").split("\n")[0] # 第一行通常是名称
            lines.append(f"ID: {item_id} | Name: {name}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取 {metadata_type} 时发生异常：{e}"


async def fetch_unprocessed_memos(tool_context: ToolContext = None) -> str:
    """从 Logseq 库中查询 class:: [[Initiative]] 且 status:: [[Planning]] 的记录。"""
    try:
        data = await _call_logseq_tool(
            "search",
            {"query": "class:: [[Initiative]] status:: [[Planning]]"},
            tool_context,
        )
        results = data.get("results", [])
        if not results:
            return "当前 Logseq 库中没有待处理（Planning）的 Initiative 项目。"

        lines = ["以下是待处理的诉求/备忘（来自 Logseq Initiative）：\n"]
        for i, item in enumerate(results, start=1):
            item_id = item.get("uuid", "")
            content = item.get("content", "").split("\n")[0]
            lines.append(f"{i}. [{item_id}] {content}")
        lines.append("\n这些项目可以被分解为 FEATURE 或 TASK，或者更新其状态。")
        return "\n".join(lines)
    except Exception as e:
        return f"获取诉求失败：{e}"


async def create_initiative(
    name: str,
    risk_description: str = "",
    tool_context: ToolContext = None,
) -> str:
    """在 Logseq 中创建宏大战略目标 (Initiative)。
    
    Args:
      name: 战略目标名称。
      risk_description: 风险与挑战描述（可选）。
    """
    try:
        # 1. 创建页面/块
        data = await _call_logseq_tool(
            "create_block",
            {"content": name, "parent_page": f"Initiative/{name}"},
            tool_context
        )
        block_uuid = data.get("uuid")
        
        # 2. 设置属性
        properties = {
            "class": "[[Initiative]]",
            "status": "[[Planning]]",
        }
        if risk_description:
            properties["risk-description"] = risk_description
            
        for k, v in properties.items():
            await _call_logseq_tool(
                "upsert_block_property",
                {"block_uuid": block_uuid, "property": k, "value": v},
                tool_context
            )
            
        return f"SUCCESS: created initiative '{name}' with UUID {block_uuid}"
    except Exception as e:
        return f"创建 Initiative 时发生异常：{e}"


async def create_feature(
    name: str,
    initiative_id: str = "",
    acceptance_criteria: str = "",
    tool_context: ToolContext = None,
) -> str:
    """在 Logseq 中创建业务功能或阶段性项目 (Feature)。
    
    Args:
      name: 项目群/业务特性名称。
      initiative_id: 若它服务于某顶层战略，填入 Initiative UUID（可选）。
      acceptance_criteria: 验收标准/发布要求（可选）。
    """
    try:
        # 1. 创建块
        data = await _call_logseq_tool(
            "create_block",
            {"content": name, "parent_page": f"Feature/{name}"},
            tool_context
        )
        block_uuid = data.get("uuid")
        
        # 2. 设置属性
        properties = {
            "class": "[[Feature]]",
            "status": "[[Active]]",
        }
        if initiative_id:
            properties["initiative"] = f"(({initiative_id}))"
        if acceptance_criteria:
            properties["acceptance-criteria"] = acceptance_criteria
            
        for k, v in properties.items():
            await _call_logseq_tool(
                "upsert_block_property",
                {"block_uuid": block_uuid, "property": k, "value": v},
                tool_context
            )
            
        return f"SUCCESS: created feature '{name}' with UUID {block_uuid}"
    except Exception as e:
        return f"创建 Feature 时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: create_task (原子级)
# ---------------------------------------------------------------------------
async def create_task(
    title: str,
    module_id: str,
    resource_id: str,
    estimated_hours: float,
    feature_id: str = "",
    initiative_id: str = "",
    description: str = "",
    todo_list: list[str] = [],
    due_date: str = "",
    tool_context: ToolContext = None,
) -> str:
    """在 Logseq 中创建最小执行原子 (Task/Flow)。"""
    if not module_id or not resource_id or estimated_hours is None:
        raise ValueError("Error: module_id, resource_id 和 estimated_hours 是强制必填参数！Task 必须有物理归属、执行人和预估工时！")

    try:
        # 1. 创建块
        parent_id = feature_id if feature_id else f"Tasks/{title}"
        data = await _call_logseq_tool(
            "create_block",
            {"content": title, "parent_page": parent_id},
            tool_context
        )
        block_uuid = data.get("uuid")
        
        # 2. 设置属性 (Atomization: Flow + Module + Resource + Information)
        properties = {
            "class": "[[Task]]",
            "module": f"(({module_id}))",
            "resource": f"(({resource_id}))",
            "estimated-hours": str(estimated_hours),
            "status": "[[Todo]]",
        }
        if initiative_id:
            properties["initiative"] = f"(({initiative_id}))"
        if due_date:
            properties["due-date"] = due_date
        if description:
            properties["description"] = description
            
        for k, v in properties.items():
            await _call_logseq_tool(
                "upsert_block_property",
                {"block_uuid": block_uuid, "property": k, "value": v},
                tool_context
            )
            
        # 3. 创建子块 (Checklist/Flow steps)
        if todo_list:
            for item in todo_list:
                await _call_logseq_tool(
                    "create_block",
                    {"content": f"TODO {item}", "parent_block_uuid": block_uuid},
                    tool_context
                )
                
        return f"SUCCESS: created task '{title}' with UUID {block_uuid}"
    except Exception as e:
        return f"创建 Task 时发生异常：{e}"


async def mark_memo_as_assigned(
    memo_id: str,
    tool_context: ToolContext = None,
) -> str:
    """将指定诉求(Initiative)的状态更新为"Active"以完成闭环。"""
    try:
        await _call_logseq_tool(
            "upsert_block_property",
            {"block_uuid": memo_id, "property": "status", "value": "[[Active]]"},
            tool_context
        )
        return f"SUCCESS: 诉求 {memo_id} 状态已更新为「Active」。"
    except Exception as e:
        return f"发生异常：{e}"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
fetch_unprocessed_memos_tool = FunctionTool(func=fetch_unprocessed_memos)
query_logseq_metadata_tool = FunctionTool(func=query_logseq_metadata)
create_initiative_tool = FunctionTool(func=create_initiative)
create_feature_tool = FunctionTool(func=create_feature)
create_task_tool = FunctionTool(func=create_task)
mark_memo_as_assigned_tool = FunctionTool(func=mark_memo_as_assigned)
