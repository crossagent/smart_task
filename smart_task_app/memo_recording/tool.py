import os
import json
from google.adk.tools import FunctionTool, ToolContext

from smart_task_app.shared_libraries.logseq_util import get_logseq_mcp_tool


def _save_memo_to_state(
    tool_context: ToolContext,
    task_content: str,
    background: str,
    related_files: str,
    requester: str,
) -> None:
    """Keep memo fields in ADK session state up to date."""
    if tool_context is None:
        return
    tool_context.state["memo_task_content"] = task_content
    tool_context.state["memo_background"] = background
    tool_context.state["memo_related_files"] = related_files
    tool_context.state["memo_requester"] = requester

async def format_memo_template(
    task_content: str,
    requester: str,
    background: str = "",
    related_files: str = "",
    tool_context: ToolContext = None
) -> str:
    """在将备忘录写入 Logseq 之前，提供确认模板。"""
    _save_memo_to_state(tool_context, task_content, background, related_files, requester)

    template = f"""
请向用户展示以下备忘录草稿，并询问是否确认写入：

【新增备忘录 - 待确认】
💡 任务内容：{task_content}
📝 背景上下文：{background or '无'}
📎 相关文件/链接：{related_files or '无'}
👤 需求方/发起人：{requester}

请问是否需要修改？或者确认无误后，我将直接写入 Logseq。
"""
    return template


async def _resolve_initiator_id(name: str, tool_context: ToolContext) -> str | None:
    """Try to find the Resource UUID for a given initiator name in Logseq."""
    try:
        data = await _call_logseq_tool(
            "search",
            {"query": f"class:: [[Resource]] {name}"},
            tool_context
        )
        results = data.get("results", [])
        if results:
            return results[0].get("uuid")
    except Exception:
        pass
    return None

async def _call_logseq_tool(tool_name: str, args: dict, tool_context: ToolContext):
    """Proxy call to Logseq MCP tools."""
    toolset = get_logseq_mcp_tool()
    tools = await toolset.get_tools()
    target = next((t for t in tools if t.name == tool_name), None)
    if target is None:
        raise ValueError(f"Logseq tool {tool_name} not found")
    res = await target.run_async(args=args, tool_context=tool_context)
    if hasattr(res, "content"):
        return json.loads(res.content[0].text)
    return json.loads(res) if isinstance(res, str) else res


async def insert_memo_record(
    task_content: str,
    requester: str,
    background: str = "",
    related_files: str = "",
    tool_context: ToolContext = None
) -> str:
    """用户确认诉求内容无误后，将其作为 Initiative 记录写入 Logseq。"""
    if not requester:
        return "错误：发起人（requester）为必填项，不可为空。"

    # Resolve Initiator (Resource)
    initiator_uuid = await _resolve_initiator_id(requester, tool_context)

    try:
        # 1. 创建页面/块
        page_name = f"Initiative/{task_content[:50]}"
        data = await _call_logseq_tool(
            "create_block",
            {"content": task_content, "parent_page": page_name},
            tool_context
        )
        block_uuid = data.get("uuid")

        # 2. 设置属性
        properties = {
            "class": "[[Initiative]]",
            "status": "[[Planning]]",
        }
        if initiator_uuid:
            properties["initiator"] = f"(({initiator_uuid}))"
        else:
            properties["initiator-raw"] = requester
            
        if background:
            properties["background"] = background
        if related_files:
            properties["related-files"] = related_files

        for k, v in properties.items():
            await _call_logseq_tool(
                "upsert_block_property",
                {"block_uuid": block_uuid, "property": k, "value": v},
                tool_context
            )
            
        return f"成功录入甲方诉求 (Initiative)！已存入 Logseq 页面: {page_name}\nUUID: {block_uuid}"
    except Exception as e:
        return f"录入诉求时发生异常：{str(e)}"

format_memo_template_tool = FunctionTool(func=format_memo_template)
insert_memo_record_tool = FunctionTool(func=insert_memo_record)
