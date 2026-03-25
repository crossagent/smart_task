from __future__ import annotations

import json
import os

from google.adk.tools import FunctionTool, ToolContext

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_db_id(env_var: str, default_val: str) -> str:
    return os.environ.get(env_var, default_val)

def _get_task_db_id() -> str:
    return _get_db_id("NOTION_TASK_DATABASE_ID", "32e0d59d-ebb7-8044-93e9-000ba6f9ab3d")

def _get_feature_db_id() -> str:
    return _get_db_id("NOTION_FEATURE_DATABASE_ID", "32e0d59d-ebb7-8001-8bd0-000b1fd12363")

def _get_initiative_db_id() -> str:
    return _get_db_id("NOTION_INITIATIVE_DATABASE_ID", "32e0d59d-ebb7-80c7-88a1-000b493dcc61")

def _get_module_db_id() -> str:
    return _get_db_id("NOTION_MODULE_DATABASE_ID", "32e0d59d-ebb7-80e7-8f18-000b37afcab4")

def _get_resource_db_id() -> str:
    return _get_db_id("NOTION_RESOURCE_DATABASE_ID", "32e0d59d-ebb7-8070-a498-000b7430b8b1")


async def _call_notion_tool(tool_name: str, args: dict, tool_context: ToolContext):
    """Call a Notion MCP tool by name and return the parsed JSON response."""
    from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool  # pylint: disable=import-outside-toplevel

    toolset = get_notion_mcp_tool()
    tools = await toolset.get_tools()
    target = next((t for t in tools if t.name == tool_name), None)
    if target is None:
        raise ValueError(f"Notion MCP tool '{tool_name}' not found.")
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

# ---------------------------------------------------------------------------
# Tool: query_notion_metadata
# ---------------------------------------------------------------------------
async def query_notion_metadata(
    metadata_type: str,
    tool_context: ToolContext = None
) -> str:
    """查询具体的元数据库（module, resource, feature, initiative）内容。
    
    使用该工具来获取目前系统中有哪些存在的 Module，Resource，Feature 或 Initiative 及其对应的 Page ID。
    
    Args:
      metadata_type: 必须是 'module', 'resource', 'feature' 或 'initiative' 中的一个。
      
    Returns:
      返回对应类型的所有记录的 名称 与 ID 的列表字符串格式，供你在创建对象时引用。
    """
    db_map = {
        "module": _get_module_db_id(),
        "resource": _get_resource_db_id(),
        "feature": _get_feature_db_id(),
        "initiative": _get_initiative_db_id()
    }
    
    if metadata_type.lower() not in db_map:
        return f"Error: 无法识别的元数据类型 '{metadata_type}'。请选择 'module', 'resource', 'feature' 或 'initiative'。"
        
    db_id = db_map[metadata_type.lower()]
    
    try:
        data = await _call_notion_tool(
            "API-query-data-source",
            {"data_source_id": db_id},
            tool_context
        )
        results = data.get("results", [])
        if not results:
            return f"没有找到任何 {metadata_type} 数据。"
            
        lines = [f"=== 当前系统中的 {metadata_type.upper()} 列表 ==="]
        for page in results:
            page_id = page.get("id", "")
            props = page.get("properties", {})
            
            # Find the title property (could be "Name", "title", etc.)
            title_prop = next((p for p in props.values() if p.get("type") == "title"), {})
            title_text = ""
            for t in title_prop.get("title", []):
                title_text += t.get("plain_text", "")
                
            lines.append(f"ID: {page_id} | Name: {title_text}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取 {metadata_type} 时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: fetch_unprocessed_memos
# ---------------------------------------------------------------------------
async def fetch_unprocessed_memos(tool_context: ToolContext = None) -> str:
    """从「备忘与诉求」(Initiative) 数据库查询 Status='Planning' 的记录，以结构化格式返回。"""
    initiative_db_id = _get_initiative_db_id()
    filter_arg = {
        "property": "Status",
        "select": {"equals": "Planning"},
    }
    try:
        data = await _call_notion_tool(
            "API-query-data-source",
            {"data_source_id": initiative_db_id, "filter": filter_arg},
            tool_context,
        )
        results = data.get("results", [])
        memos = []
        for page in results:
            page_id = page.get("id", "")
            props = page.get("properties", {})

            # Initiative title property is "Name"
            name_prop = props.get("Name", {})
            title = ""
            for t in name_prop.get("title", []):
                title += t.get("plain_text", "")

            memos.append({"id": page_id, "title": title})

        if not memos:
            return "当前「备忘与诉求」库中没有待处理（Planning）的项目。"

        lines = ["以下是待处理的诉求/备忘（来自 Inbox & Initiative）：\n"]
        for i, m in enumerate(memos, start=1):
            lines.append(f"{i}. [{m['id']}] {m['title']}")
        lines.append("\n这些项目可以被分解为 FEATURE 或 TASK，或者更新其状态。")
        return "\n".join(lines)
    except Exception as e:
        return f"获取诉求失败：{e}"


# ---------------------------------------------------------------------------
# Tool: create_initiative (战略级)
# ---------------------------------------------------------------------------
async def create_initiative(
    name: str,
    risk_description: str = "",
    tool_context: ToolContext = None,
) -> str:
    """在 Initiative 数据库中创建宏大战略目标。
    注意：Initiative 是顶层视图，不允许挂载物理资源或执行人！
    
    Args:
      name: 战略目标名称。
      risk_description: 风险与挑战描述（可选）。
    """
    db_id = _get_initiative_db_id()
    properties: dict = {
        "Name": {"title": [{"text": {"content": name}}]},
    }
    
    children = []
    if risk_description:
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "核心风险与里程碑"}}]}
        })
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": risk_description}}]}
        })

    notion_args = {"parent": {"data_source_id": db_id}, "properties": properties}
    if children:
        notion_args["children"] = children

    try:
        data = await _call_notion_tool("API-post-page", notion_args, tool_context)
        if data.get("object") == "error":
            return f"创建 Initiative 失败：{data.get('message')}"
        return f"SUCCESS: created initiative '{name}' with ID {data.get('id', '')}"
    except Exception as e:
        return f"创建 Initiative 时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: create_feature (业务级)
# ---------------------------------------------------------------------------
async def create_feature(
    name: str,
    initiative_id: str = "",
    acceptance_criteria: str = "",
    tool_context: ToolContext = None,
) -> str:
    """在 Feature 数据库中创建业务功能或阶段性项目。
    注意：Feature 允许向顶层挂载 Initiative，但绝不允许绑定单一物理 Module 
    或 Resource！因为它代表一个横跨多个模块的任务群。
    
    Args:
      name: 项目群/业务特性名称。
      initiative_id: 若它服务于某顶层战略，填入 Initiative Page ID（可选）。
      acceptance_criteria: 验收标准/发布要求（可选）。
    """
    db_id = _get_feature_db_id()
    properties: dict = {
        "Name": {"title": [{"text": {"content": name}}]},
    }
    if initiative_id:
        properties["Initiative"] = {"relation": [{"id": initiative_id}]}

    children = []
    if acceptance_criteria:
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "验收标准"}}]}
        })
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": acceptance_criteria}}]}
        })

    notion_args = {"parent": {"data_source_id": db_id}, "properties": properties}
    if children:
        notion_args["children"] = children

    try:
        data = await _call_notion_tool("API-post-page", notion_args, tool_context)
        if data.get("object") == "error":
            return f"创建 Feature 失败：{data.get('message')}"
        return f"SUCCESS: created feature '{name}' with ID {data.get('id', '')}"
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
    """在 Task 数据库中创建最小执行原子。

    【强制约束】：每一个 Task 都必须有明确的物理归属和执行人。不允许挂载到 Initiative。
    如果缺少合法参数，将被拒绝。
    
    Args:
      title: 任务标题。
      module_id: **必须填写**！物理归属模块的 Page ID。
      resource_id: **必须填写**！执行人的 Page ID。
      feature_id: 当前关联的业务特性组 Page ID (可选)。
      initiative_id: 当前关联的甲方诉求/战略 ID (可选)。
      description: 任务详情描述 (可选)。
      todo_list: 具体的执行步骤列表，将作为打勾项写入正文 (可选)。
      due_date: 截止日期 'YYYY-MM-DD' (可选)。
    """
    if not module_id or not resource_id or estimated_hours is None:
        raise ValueError("Error: module_id, resource_id 和 estimated_hours 是强制必填参数！Task 必须有物理归属、执行人和预估工时！")

    task_db_id = _get_task_db_id()
    properties: dict = {
        "Name": {"title": [{"text": {"content": title}}]},
        "Module": {"relation": [{"id": module_id}]},
        "Resource": {"relation": [{"id": resource_id}]},
        "Estimated_Hours": {"number": float(estimated_hours)},
    }
    
    if feature_id:
        properties["Feature"] = {"relation": [{"id": feature_id}]}
        
    if initiative_id:
        properties["Initiative"] = {"relation": [{"id": initiative_id}]}
        
    if due_date:
        # For new tasks, we usually only have a target end date or a single day assignment
        properties["Timeline"] = {"date": {"start": due_date}}

    children = []
    if description:
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": description}}]}
        })

    if todo_list:
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "执行步骤 / Checklist"}}]}
        })
        for item in todo_list:
            children.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": str(item)}}],
                    "checked": False
                }
            })

    notion_args = {"parent": {"data_source_id": task_db_id}, "properties": properties}
    if children:
        notion_args["children"] = children

    try:
        data = await _call_notion_tool("API-post-page", notion_args, tool_context)
        if data.get("object") == "error":
            return f"创建 Task 失败：{data.get('message')}"
        return f"SUCCESS: created task '{title}' with ID {data.get('id', '')}"
    except Exception as e:
        return f"创建 Task 时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: mark_memo_as_assigned
# ---------------------------------------------------------------------------
async def mark_memo_as_assigned(
    memo_id: str,
    tool_context: ToolContext = None,
) -> str:
    """将指定诉求(Initiative)的状态更新为"Active"以完成闭环。"""
    notion_args = {
        "page_id": memo_id,
        "properties": {"Status": {"select": {"name": "Active"}}},
    }
    try:
        data = await _call_notion_tool("API-patch-page", notion_args, tool_context)
        if data.get("object") == "error":
            return f"更新状态失败：{data.get('message')}"
        return f"SUCCESS: 诉求 {memo_id} 状态已更新为「Active」。"
    except Exception as e:
        return f"发生异常：{e}"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
fetch_unprocessed_memos_tool = FunctionTool(func=fetch_unprocessed_memos)
query_notion_metadata_tool = FunctionTool(func=query_notion_metadata)
create_initiative_tool = FunctionTool(func=create_initiative)
create_feature_tool = FunctionTool(func=create_feature)
create_task_tool = FunctionTool(func=create_task)
mark_memo_as_assigned_tool = FunctionTool(func=mark_memo_as_assigned)
