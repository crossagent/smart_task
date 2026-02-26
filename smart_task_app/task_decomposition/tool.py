from __future__ import annotations

import json
import os

from google.adk.tools import FunctionTool, ToolContext


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_task_db_id() -> str:
  return os.environ.get(
      "NOTION_TASK_DATABASE_ID",
      "1990d59d-ebb7-816d-ab7b-f83e93458d30",
  )


def _get_project_db_id() -> str:
  return os.environ.get(
      "NOTION_PROJECT_DATABASE_ID",
      "1990d59d-ebb7-81c5-8d78-c302dffea2b5",
  )


def _get_memo_db_id() -> str:
  return os.environ.get(
      "NOTION_MEMO_DATABASE_ID",
      "3120d59d-ebb7-808d-a582-d4baae4fe44b",
  )


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
    # ADK ToolResponse dictionary format
    content_text = raw["content"][0].get("text", "{}")
    return json.loads(content_text)
  if hasattr(raw, "content"):
    # ToolResponse object format
    return json.loads(raw.content[0].text)

  return raw


# ---------------------------------------------------------------------------
# Tool: fetch_unprocessed_memos
# ---------------------------------------------------------------------------

async def fetch_unprocessed_memos(tool_context: ToolContext = None) -> str:
  """从备忘录数据库查询 State='未处理' 的记录，以结构化 JSON 列表返回。

  每条记录包含 id, title, background, requester 字段。
  """
  memo_db_id = _get_memo_db_id()
  filter_arg = {
      "property": "State",
      "status": {"equals": "未处理"},
  }
  try:
    data = await _call_notion_tool(
        "API-query-data-source",
        {"data_source_id": memo_db_id, "filter": filter_arg},
        tool_context,
    )
    results = data.get("results", [])
    memos = []
    for page in results:
      page_id = page.get("id", "")
      props = page.get("properties", {})

      # Title field named "Note"
      note_prop = props.get("Note", {})
      title = ""
      for t in note_prop.get("title", []):
        title += t.get("plain_text", "")

      # Read page body blocks for background / requester (best-effort)
      memos.append({"id": page_id, "title": title})

    if not memos:
      return "当前没有未处理的备忘录。"

    lines = ["以下是未处理的备忘录：\n"]
    for i, m in enumerate(memos, start=1):
      lines.append(f"{i}. [{m['id']}] {m['title']}")
    lines.append("\n请告诉我你想处理哪一条？")
    return "\n".join(lines)
  except Exception as e:  # pylint: disable=broad-except
    return f"获取备忘录失败：{e}"


# ---------------------------------------------------------------------------
# Tool: create_project
# ---------------------------------------------------------------------------

async def create_project(
    name: str,
    goal: str = "",
    due_date: str = "",
    tool_context: ToolContext = None,
) -> str:
  """在 Project 数据库中创建一个新项目，返回新项目的 page_id。

  Args:
    name: 项目名称。
    goal: 项目目标描述（可选）。
    due_date: 截止日期，ISO 8601 格式，如 '2026-03-15'（可选）。

  Returns:
    创建成功时返回 'project_id:<新项目的page_id>'，失败时返回错误信息。
  """
  project_db_id = _get_project_db_id()
  properties: dict = {
      "Project name": {"title": [{"text": {"content": name}}]},
  }
  if due_date:
    properties["Dates"] = {"date": {"start": due_date}}

  children = []
  if goal:
    children.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "项目目标"}}]
        },
    })
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": goal}}]
        },
    })

  notion_args: dict = {
      "parent": {"database_id": project_db_id},
      "properties": properties,
  }
  if children:
    notion_args["children"] = children

  try:
    data = await _call_notion_tool("API-post-page", notion_args, tool_context)
    if data.get("object") == "error":
      return f"创建项目失败：{data.get('message')}"
    page_id = data.get("id", "")
    return f"project_id:{page_id}"
  except Exception as e:  # pylint: disable=broad-except
    return f"创建项目时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: create_task
# ---------------------------------------------------------------------------

async def create_task(
    title: str,
    project_id: str = "",
    due_date: str = "",
    assignee: str = "",
    background: str = "",
    tool_context: ToolContext = None,
) -> str:
  """在 Task 数据库中创建一个顶层任务，返回新任务的 page_id。

  Args:
    title: 任务标题。
    project_id: 关联的 Project page_id（可为空）。
    due_date: 截止日期，ISO 8601 格式（可选）。
    assignee: 负责人姓名（可选，填入任务正文）。
    background: 背景说明（可选，填入任务正文）。

  Returns:
    创建成功时返回 'task_id:<新任务的page_id>'，失败时返回错误信息。
  """
  task_db_id = _get_task_db_id()
  properties: dict = {
      "Task name": {"title": [{"text": {"content": title}}]},
  }
  if due_date:
    properties["Due"] = {"date": {"start": due_date}}
  if project_id:
    # Notion relation property - field name may vary; "Project" is common
    properties["Project"] = {"relation": [{"id": project_id}]}

  children = []
  if background:
    children.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "背景"}}]
        },
    })
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": background}}]
        },
    })
  if assignee:
    children.append({
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{
                "type": "text",
                "text": {"content": f"负责人：{assignee}"},
            }]
        },
    })

  notion_args: dict = {
      "parent": {"database_id": task_db_id},
      "properties": properties,
  }
  if children:
    notion_args["children"] = children

  try:
    data = await _call_notion_tool("API-post-page", notion_args, tool_context)
    if data.get("object") == "error":
      return f"创建任务失败：{data.get('message')}"
    page_id = data.get("id", "")
    return f"task_id:{page_id}"
  except Exception as e:  # pylint: disable=broad-except
    return f"创建任务时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: create_subtask
# ---------------------------------------------------------------------------

async def create_subtask(
    title: str,
    parent_task_id: str,
    due_date: str = "",
    tool_context: ToolContext = None,
) -> str:
  """在 Task 数据库中创建子任务（Notion sub-item），挂载在父任务下。

  子任务层级不超过 2 层（即：任务 → 子任务），不可再创建子任务的子任务。

  Args:
    title: 子任务标题。
    parent_task_id: 父任务的 page_id，子任务将作为其 sub-item。
    due_date: 截止日期，ISO 8601 格式（可选）。

  Returns:
    创建成功时返回 'subtask_id:<新子任务的page_id>'，失败时返回错误信息。
  """
  properties: dict = {
      "Task name": {"title": [{"text": {"content": title}}]},
  }
  if due_date:
    properties["Due"] = {"date": {"start": due_date}}

  task_db_id = _get_task_db_id()
  # Link to parent task via relation property
  properties["Parent-task"] = {"relation": [{"id": parent_task_id}]}

  notion_args = {
      "parent": {"database_id": task_db_id},
      "properties": properties,
  }

  try:
    data = await _call_notion_tool("API-post-page", notion_args, tool_context)
    if data.get("object") == "error":
      return f"创建子任务失败：{data.get('message')}"
    page_id = data.get("id", "")
    return f"subtask_id:{page_id}"
  except Exception as e:  # pylint: disable=broad-except
    return f"创建子任务时发生异常：{e}"


# ---------------------------------------------------------------------------
# Tool: mark_memo_as_assigned
# ---------------------------------------------------------------------------

async def mark_memo_as_assigned(
    memo_id: str,
    tool_context: ToolContext = None,
) -> str:
  """将指定备忘录的 State 属性从"未处理"更新为"已分配任务"。

  Args:
    memo_id: 备忘录的 Notion page_id。

  Returns:
    操作结果描述字符串。
  """
  notion_args = {
      "page_id": memo_id,
      "properties": {
          "State": {"status": {"name": "已分配任务"}},
      },
  }
  try:
    data = await _call_notion_tool("API-patch-page", notion_args, tool_context)
    if data.get("object") == "error":
      return f"更新备忘录状态失败：{data.get('message')}"
    return f"备忘录 {memo_id} 状态已更新为「已分配任务」。"
  except Exception as e:  # pylint: disable=broad-except
    return f"更新备忘录状态时发生异常：{e}"


# ---------------------------------------------------------------------------
# FunctionTool exports
# ---------------------------------------------------------------------------

fetch_unprocessed_memos_tool = FunctionTool(func=fetch_unprocessed_memos)
create_project_tool = FunctionTool(func=create_project)
create_task_tool = FunctionTool(func=create_task)
create_subtask_tool = FunctionTool(func=create_subtask)
mark_memo_as_assigned_tool = FunctionTool(func=mark_memo_as_assigned)
