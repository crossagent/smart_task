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
    background: str = "",
    related_files: str = "",
    requester: str = "",
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
👤 需求方：{requester or '未指定'}

请问是否需要修改？或者确认无误后，我将直接写入系统。
"""
    return template


async def insert_memo_record(
    task_content: str,
    background: str = "",
    related_files: str = "",
    requester: str = "",
    tool_context: ToolContext = None
) -> str:
    """用户确认备忘录内容无误后，调用此工具将数据格式化为Notion API所需的JSON并写入数据库。此工具必须在format_memo_template并取得用户确认后使用。"""
    memo_db_id = os.environ.get('NOTION_MEMO_DATABASE_ID')
    if not memo_db_id:
        return "错误：未配置 NOTION_MEMO_DATABASE_ID 环境变量。"

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
        
    if requester:
        children_blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "需求方"}}]}
        })
        children_blocks.append({
             "object": "block",
             "type": "paragraph",
             "paragraph": {"rich_text": [{"type": "text", "text": {"content": requester}}]}
        })

    notion_args = {
        "parent": {
            "type": "database_id",
            "database_id": memo_db_id
        },
        "properties": {
            "Note": {
                "title": [
                    {
                        "text": {
                            "content": task_content
                        }
                    }
                ]
            },
            "State": {
                "select": {
                    "name": "未处理"
                }
            }
        },
        "children": children_blocks
    }

    notion_toolset = get_notion_mcp_tool()
    
    # 提取底层的API-post-page工具
    api_post_page = None
    tools = await notion_toolset.get_tools()
    for tool in tools:
        if tool.name == "API-post-page":
            api_post_page = tool
            break
            
    if not api_post_page:
        return "错误：无法在Notion MCP中找到 API-post-page 工具。"
        
    try:
        # 代理调用 Notion MCP 工具
        result = await api_post_page.run_async(args=notion_args, tool_context=tool_context)

        # Update state with the actually-committed memo content.
        _save_memo_to_state(tool_context, task_content, background, related_files, requester)

        return f"成功插入备忘录！Notion 返回结果：\n{result}"
    except Exception as e:
        return f"插入备忘录时发生异常：{str(e)}"

format_memo_template_tool = FunctionTool(func=format_memo_template)
insert_memo_record_tool = FunctionTool(func=insert_memo_record)
