import os
import json
from google.adk.tools import FunctionTool, ToolContext

from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool


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
    """在将备忘录写入Notion之前，提供收集到的信息，生成一个标准的确认模板返回给大模型，大模型借此向用户确认。"""
    # Persist the draft into session state so downstream tools/agents can read
    # them without requiring the LLM to re-pass the arguments.
    _save_memo_to_state(tool_context, task_content, background, related_files, requester)

    template = f"""
请向用户展示以下备忘录草稿，并询问是否确认写入：

【新增备忘录 - 待确认】
💡 任务内容：{task_content}
📝 背景上下文：{background or '无'}
📎 相关文件/链接：{related_files or '无'}
👤 需求方/发起人：{requester}

请问是否需要修改？或者确认无误后，我将直接写入系统。
"""
    return template


async def _resolve_initiator_id(name: str, tool_context: ToolContext) -> str | None:
    """Try to find the Resource Page ID for a given initiator name."""
    resource_db_id = os.environ.get('NOTION_RESOURCE_DATABASE_ID', '32e0d59d-ebb7-8070-a498-000b7430b8b1')
    try:
        data = await _call_notion_tool(
            "API-query-data-source",
            {
                "data_source_id": resource_db_id,
                "filter": {
                    "property": "Name",
                    "title": {"contains": name}
                }
            },
            tool_context
        )
        results = data.get("results", [])
        if results:
            # Prefer exact match if possible
            for res in results:
                props = res.get("properties", {})
                title_list = props.get("Name", {}).get("title", [])
                full_name = "".join([t.get("plain_text", "") for t in title_list])
                if full_name == name:
                    return res.get("id")
            return results[0].get("id")
    except Exception:
        pass
    return None

async def _call_notion_tool(tool_name: str, args: dict, tool_context: ToolContext):
    """Proxy call to Notion MCP tools."""
    notion_toolset = get_notion_mcp_tool()
    api_tool = None
    tools = await notion_toolset.get_tools()
    for tool in tools:
        if tool.name == tool_name:
            api_tool = tool
            break
    if not api_tool:
        raise ValueError(f"Notion tool {tool_name} not found")
    return await api_tool.run_async(args=args, tool_context=tool_context)


async def insert_memo_record(
    task_content: str,
    requester: str,
    background: str = "",
    related_files: str = "",
    tool_context: ToolContext = None
) -> str:
    """用户确认诉求内容无误后，将其作为 Initiative 记录写入 Notion。"""
    if not requester:
        return "错误：发起人（requester）为必填项，不可为空。"

    initiative_db_id = os.environ.get('NOTION_INITIATIVE_DATABASE_ID', '32e0d59d-ebb7-80c7-88a1-000b493dcc61')

    # Resolve Initiator (Resource)
    initiator_id = await _resolve_initiator_id(requester, tool_context)

    # 构造 Notion 页面内容
    children_blocks = []
    if background:
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "背景信息"}}]}
        })
        children_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": background}}]}
        })
    
    if related_files:
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "相关文件/链接"}}]}
        })
        children_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": related_files}}]}
        })
        
    if requester and not initiator_id:
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "需求方 (未关联)"}}]}
        })
        children_blocks.append({
             "object": "block",
             "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": requester}}]}
        })

    properties = {
        "Name": {
            "title": [{"text": {"content": task_content}}]
        },
        "Status": {
            "select": {"name": "Planning"}
        }
    }

    if initiator_id:
        properties["Initiator"] = {"relation": [{"id": initiator_id}]}

    notion_args = {
        "parent": {
            "type": "data_source_id",
            "data_source_id": initiative_db_id
        },
        "properties": properties,
        "children": children_blocks
    }
        
    try:
        result = await _call_notion_tool("API-post-page", notion_args, tool_context)
        _save_memo_to_state(tool_context, task_content, background, related_files, requester)
        initiator_status = f"(已关联资源: {requester})" if initiator_id else f"(未找到资源: {requester}，已存入正文)"
        return f"成功录入甲方诉求 (Initiative)！{initiator_status}\nNotion 返回结果 ID: {result.get('id', 'N/A') if isinstance(result, dict) else 'OK'}"
    except Exception as e:
        return f"录入诉求时发生异常：{str(e)}"

format_memo_template_tool = FunctionTool(func=format_memo_template)
insert_memo_record_tool = FunctionTool(func=insert_memo_record)
