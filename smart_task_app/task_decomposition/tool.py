from __future__ import annotations

import json
import os
import asyncio
from google.adk.tools import FunctionTool, ToolContext

# ---------------------------------------------------------------------------
# Internal helpers (Pure Logseq)
# ---------------------------------------------------------------------------

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

async def _datalog_query(query: str, tool_context: ToolContext = None) -> list:
    """Helper to perform native Datalog queries against the Logseq DB."""
    data = await _call_logseq_tool(
        "datascript_query",
        {"query": query},
        tool_context
    )
    return data.get("results", [])

# ---------------------------------------------------------------------------
# Metadata Queries (Now Pure Logseq / Datalog)
# ---------------------------------------------------------------------------

async def query_logseq_metadata(
    metadata_type: str,
    tool_context: ToolContext = None
) -> str:
    """查询具体的元数级实体（module, resource, feature, event）内容。"""
    valid_types = ["module", "resource", "feature", "event"]
    if metadata_type.lower() not in valid_types:
        return f"Error: 无法识别 '{metadata_type}'。"
        
    class_name = metadata_type.capitalize()
    
    # 极速版：只拉取 content 和 uuid，不拉取所有元数据
    query = f'[:find ?uuid ?content :where [?b :block/uuid ?uuid] [?b :block/content ?content] [?b :block/properties ?p] [(get ?p :class) ?c] [(= ?c "[[{class_name}]]")]]'
    
    try:
        results = await _datalog_query(query, tool_context)
        if not results: return f"没有找到任何 {class_name} 数据。"
            
        lines = [f"=== Logseq 实时图谱中的 {class_name} 列表 ==="]
        for uuid, content in results:
            lines.append(f"ID: {uuid} | Name: {content.split('\n')[0]}")
        return "\n".join(lines)
    except Exception as e:
        return f"查询 {metadata_type} 时超时或异常：{e}"

async def audit_tasks_health(tool_context: ToolContext = None) -> str:
    """对当前全谱任务进行审计并导出 CSV 格式报告以便 Review。"""
    # 找到所有 Task 的基本信息
    query = '[:find ?uuid ?content :where [?b :block/uuid ?uuid] [?b :block/content ?content] [?b :block/properties ?p] [(get ?p :class) ?c] [(= ?c "[[Task]]")]]'
    try:
        results = await _datalog_query(query, tool_context)
        if not results: return "全谱为空。"
            
        audit_results = ["UUID,Name,Status,Events,Features,Modules,Resources"]
        for uuid, content in results:
            # 这是一个轻量的体检
            lines = content.split("\n")
            name = lines[0]
            props = "\n".join(lines[1:])
            
            # 标记异常
            e = "OK" if "event::" in props else "MISSING"
            f = "OK" if "feature::" in props else "NONE"
            m = "OK" if "module::" in props else "WARN"
            r = "OK" if "resource::" in props else "UNASSIGNED"
            
            audit_results.append(f"{uuid},{name},Active,{e},{f},{m},{r}")
            
        return "\n".join(audit_results)
    except Exception as e:
        return f"执行全谱审计时发生异常：{e}"

async def fetch_unprocessed_memos(tool_context: ToolContext = None) -> str:
    """从 Logseq 库中查询 class:: [[Event]] 且 status:: [[Planning]] 的记录。"""
    query = '[:find (pull ?b [*]) :where [?b :block/properties ?p] [(get ?p :class) ?cl] [(= ?cl "[[Event]]")] [(get ?p :status) ?s] [(= ?s "[[Planning]]")]]'
    try:
        results = await _datalog_query(query, tool_context)
        if not results:
            return "当前 Logseq 库中没有待处理（Planning）的 Event 事件/备忘。"

        lines = ["以下是待处理的诉求/备忘（来自 Logseq Event）：\n"]
        for i, item in enumerate(results, start=1):
            block = item[0] if isinstance(item, list) else item
            item_id = block.get("uuid", "")
            content = block.get("content", "").split("\n")[0]
            lines.append(f"{i}. [{item_id}] {content}")
        return "\n".join(lines)
    except Exception as e:
        return f"获取诉求失败：{e}"

async def create_event(name: str, initiator: str = "", deadline: str = "", tool_context: ToolContext = None) -> str:
    """在 Logseq 中创建事件/原始诉求记录 (Event)。"""
    try:
        content = f"{name}\nclass:: [[Event]]\nstatus:: [[Planning]]\nmemo-content:: {name}"
        if initiator: content += f"\ninitiator:: {initiator}"
        if deadline: content += f"\ndeadline:: {deadline}"
        await _call_logseq_tool("create_block", {"content": content, "parent_page": f"Event/{name}"}, tool_context)
        return f"SUCCESS: created event '{name}' in Logseq."
    except Exception as e:
        return f"创建 Event 失败：{e}"

async def create_feature(name: str, event_id: str = "", owner: str = "", benefit: str = "", tool_context: ToolContext = None) -> str:
    """在 Logseq 中创建业务功能或阶段性项目实现方案 (Feature)。"""
    try:
        content = f"{name}\nclass:: [[Feature]]\nstatus:: [[Active]]"
        if event_id: content += f"\nevent:: (({event_id}))"
        if owner: content += f"\nowner:: {owner}"
        if benefit: content += f"\nbenefit:: {benefit}"
        await _call_logseq_tool("create_block", {"content": content, "parent_page": f"Feature/{name}"}, tool_context)
        return f"SUCCESS: created feature '{name}' in Logseq."
    except Exception as e:
        return f"创建 Feature 失败：{e}"

async def create_task(
    title: str,
    module_id: str,
    resource_id: str,
    estimated_hours: float,
    event_id: str = "",
    feature_id: str = "",
    objective: str = "",
    todo_list: list[str] = [],
    tool_context: ToolContext = None,
) -> str:
    """在 Logseq 中创建最小执行原子 (Task)。"""
    try:
        content = f"{title}\nclass:: [[Task]]\nobjective:: {objective or title}\nestimated-hours:: {estimated_hours}\nstatus:: [[Todo]]"
        if event_id: content += f"\nevent:: (({event_id}))"
        if feature_id: content += f"\nfeature:: (({feature_id}))"
        if module_id: content += f"\nmodule:: (({module_id}))"
        if resource_id: content += f"\nresource:: (({resource_id}))"
        
        data = await _call_logseq_tool(
            "create_block",
            {"content": content, "parent_page": "Tasks"},
            tool_context
        )
        return f"SUCCESS: created task and synchronized to Logseq: {title}"
    except Exception as e:
        return f"创建 Task 失败：{e}"

async def mark_memo_as_assigned(
    memo_id: str,
    tool_context: ToolContext = None,
) -> str:
    """将指定事件/备忘(Event)的状态更新为"Active"以完成闭环。"""
    try:
        await _call_logseq_tool(
            "upsert_block_property",
            {"block_uuid": memo_id, "property": "status", "value": "[[Active]]"},
            tool_context
        )
        return f"SUCCESS: 备忘 {memo_id} 状态已更新为「Active」。"
    except Exception as e:
        return f"发生异常：{e}"


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
fetch_unprocessed_memos_tool = FunctionTool(func=fetch_unprocessed_memos)
query_logseq_metadata_tool = FunctionTool(func=query_logseq_metadata)
create_event_tool = FunctionTool(func=create_event)
create_feature_tool = FunctionTool(func=create_feature)
create_task_tool = FunctionTool(func=create_task)
mark_memo_as_assigned_tool = FunctionTool(func=mark_memo_as_assigned)
audit_tasks_health_tool = FunctionTool(func=audit_tasks_health)
