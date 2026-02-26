"""集成测试：Project（项目）数据库读写。"""

import asyncio
import json
import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

from dotenv import load_dotenv
load_dotenv()

from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool

# ============================================================================
# 项目（Project）数据库 CRUD 集成测试
#
# 【如何找到正确的 Notion Database ID】
# -------------------------------------------------------
# Notion 数据库 ID 查找的最可靠方法是通过 API 搜索（Search API）：
#
#   1. 使用 API-post-search 工具或运行搜索脚本。
#   2. 过滤结果对象为 "database"。
#   3. 从搜索结果中匹配标题（例如 "项目" 或 "Projects"）。
#   4. 确认 properties 中包含预期的字段（例如 "Project name", "Dates"）。
#
# 注意：浏览器 URL 中的 ID 可能是页面 ID 或视图 ID，不一定能直接用于数据库操作。
# 如果 POST 请求返回 400 "is a page, not a database"，说明使用的是页面 ID。
#
# 最终确认的正确项目 Database ID：
#   1990d59d-ebb7-81c5-8d78-c302dffea2b5
# ============================================================================

PROJECT_DB_ID = "1990d59d-ebb7-81c5-8d78-c302dffea2b5"


def _get_server_params():
  return get_notion_mcp_tool()._connection_params.server_params


def test_project_db_read_write_delete():
  """验证 Project DB 的写入→读取→归档删除完整流程。"""

  async def _run():
    try:
      from mcp import stdio_client, ClientSession
    except ImportError:
      pytest.skip("mcp module not installed")

    server_params = _get_server_params()
    async with stdio_client(server_params) as (read, write):
      async with ClientSession(read, write) as session:
        await session.initialize()

        # Write
        create_res = await session.call_tool(
            "API-post-page",
            {
                "parent": {"database_id": PROJECT_DB_ID},
                "properties": {
                    "Project name": {
                        "title": [{"text": {"content": "[集成测试] Project 读写测试"}}]
                    },
                    "Dates": {"date": {"start": "2026-03-01"}},
                },
            },
        )
        assert create_res.content
        data = json.loads(create_res.content[0].text)
        assert data.get("object") != "error", f"Write failed: {data.get('message')}"
        page_id = data["id"]
        print(f"\n[Test] Created project page: {data.get('url')}")

        # Read
        read_res = await session.call_tool(
            "API-retrieve-a-page", {"page_id": page_id}
        )
        assert read_res.content
        read_data = json.loads(read_res.content[0].text)
        assert read_data.get("id") == page_id
        print(f"[Test] Read back page OK: {read_data.get('url')}")

        # Delete (archive)
        del_res = await session.call_tool(
            "API-patch-page", {"page_id": page_id, "archived": True}
        )
        assert del_res.content
        del_data = json.loads(del_res.content[0].text)
        assert del_data.get("archived") is True
        print(f"[Test] Archived project page: {page_id}")

  asyncio.run(_run())


if __name__ == "__main__":
  pytest.main([__file__, "-v", "-s"])
