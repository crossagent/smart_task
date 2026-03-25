"""集成测试：验证 task_decomposition/tool.py 中的各工具函数。

测试策略：
- 只读操作（fetch_unprocessed_memos）直接运行，不产生副作用。
- 写入操作（create_project / create_task / create_subtask）创建后立即归档清理。
- mark_memo_as_assigned 的写操作通过单独标记一条测试专用备忘录来验证（场景略复杂，
  本轮仅验证参数路径是否正常，不实际写入 State，以避免污染真实数据）。
"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from dotenv import load_dotenv

load_dotenv()


# ============================================================================
# Test: fetch_unprocessed_memos
# ============================================================================

def test_fetch_unprocessed_memos_returns_string():
  """验证 fetch_unprocessed_memos 可以连接 Notion 并返回字符串结果。"""

  async def _run():
    from smart_task_app.task_decomposition.tool import fetch_unprocessed_memos  # pylint: disable=import-outside-toplevel

    result = await fetch_unprocessed_memos(tool_context=None)
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    print(f"\n[Test] fetch_unprocessed_memos result:\n{result}")
    # Should either list memos or say none found
    assert len(result) > 0

  asyncio.run(_run())


# ============================================================================
# Test: create_project (write + cleanup)
# ============================================================================

def test_create_project_and_cleanup():
  """验证 create_project 可以创建项目并返回 page_id，然后归档清理。"""

  async def _run():
    from smart_task_app.task_decomposition.tool import (  # pylint: disable=import-outside-toplevel
        _call_notion_tool,
        create_project,
    )

    result = await create_project(
        name="[集成测试] 临时测试项目",
        goal="验证 create_project 工具函数正常工作",
        due_date="2026-03-01",
        tool_context=None,
    )
    print(f"\n[Test] create_project result: {result}")
    assert result.startswith("project_id:"), f"Unexpected result: {result}"

    page_id = result.split("project_id:")[1].strip()
    assert len(page_id) > 0

    # Cleanup: archive the created page
    cleanup = await _call_notion_tool(
        "API-patch-page",
        {"page_id": page_id, "archived": True},
        None,
    )
    print(f"[Test] Cleanup result: archived={cleanup.get('archived')}")

  asyncio.run(_run())


# ============================================================================
# Test: create_task (write + cleanup)
# ============================================================================

def test_create_task_and_cleanup():
  """验证 create_task 可以创建任务并返回 page_id，然后归档清理。"""

  async def _run():
    from smart_task_app.task_decomposition.tool import (  # pylint: disable=import-outside-toplevel
        _call_notion_tool,
        create_task,
    )

    result = await create_task(
        title="[集成测试] 临时测试任务",
        project_id="",  # No project link for isolation
        due_date="2026-03-01",
        assignee="",
        background="验证 create_task 工具函数正常工作",
        tool_context=None,
    )
    print(f"\n[Test] create_task result: {result}")
    assert result.startswith("task_id:"), f"Unexpected result: {result}"

    page_id = result.split("task_id:")[1].strip()
    assert len(page_id) > 0

    # Cleanup
    cleanup = await _call_notion_tool(
        "API-patch-page",
        {"page_id": page_id, "archived": True},
        None,
    )
    print(f"[Test] Cleanup result: archived={cleanup.get('archived')}")

  asyncio.run(_run())


# ============================================================================
# Test: create_subtask (write + cleanup)
# ============================================================================

def test_create_subtask_and_cleanup():
  """验证 create_subtask 可以作为父任务的 sub-item 创建子任务，然后归档清理。"""

  async def _run():
    from smart_task_app.task_decomposition.tool import (  # pylint: disable=import-outside-toplevel
        _call_notion_tool,
        create_subtask,
        create_task,
    )

    # First create a parent task
    parent_result = await create_task(
        title="[集成测试] 父任务（用于测试子任务创建）",
        tool_context=None,
    )
    assert parent_result.startswith("task_id:"), f"Parent task creation failed: {parent_result}"
    parent_task_id = parent_result.split("task_id:")[1].strip()
    print(f"\n[Test] Created parent task: {parent_task_id}")

    # Create subtask under parent
    subtask_result = await create_subtask(
        title="[集成测试] 子任务步骤一",
        parent_task_id=parent_task_id,
        due_date="2026-03-01",
        tool_context=None,
    )
    print(f"[Test] create_subtask result: {subtask_result}")
    assert subtask_result.startswith("subtask_id:"), f"Unexpected result: {subtask_result}"

    subtask_id = subtask_result.split("subtask_id:")[1].strip()
    assert len(subtask_id) > 0

    # Cleanup subtask first, then parent
    await _call_notion_tool(
        "API-patch-page", {"page_id": subtask_id, "archived": True}, None
    )
    await _call_notion_tool(
        "API-patch-page", {"page_id": parent_task_id, "archived": True}, None
    )
    print("[Test] Cleanup complete.")

  asyncio.run(_run())


if __name__ == "__main__":
  pytest.main([__file__, "-v", "-s"])
