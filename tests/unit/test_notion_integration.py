import os
import sys
import pytest
import asyncio

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()


from smart_task_app.shared_libraries.notion_util import get_notion_mcp_tool
from google.adk.tools.mcp_tool import McpToolset

# ============================================================================
# Hardcoded Notion Database IDs
# ============================================================================
NOTION_TASK_DATABASE_ID = "1990d59d-ebb7-815d-92a9-000be178f9ac"
NOTION_PROJECT_DATABASE_ID = "1990d59d-ebb7-812d-83c2-000bdfa9dc64"
NOTION_MEMO_DATABASE_ID = "3120d59d-ebb7-808d-a582-d4baae4fe44b"

def test_singleton_instance():
    """Verify that get_notion_mcp_tool returns the same instance."""
    tool1 = get_notion_mcp_tool()
    tool2 = get_notion_mcp_tool()
    
    assert tool1 is tool2
    assert isinstance(tool1, McpToolset)

def test_mcp_server_connectivity():
    """
    Integration test to verify the MCP server is actually reachable and returns tools.
    This creates a direct Stdio Client connection using the parameters from the toolset.
    """
    async def _test_logic():
        toolset = get_notion_mcp_tool()
        # Access private attribute for verification
        params = toolset._connection_params
        
        # We expect StdioConnectionParams
        assert hasattr(params, 'server_params')
        server_params = params.server_params
        
        print(f"\n[Test] Connecting to: {server_params.command} {server_params.args}")
        
        # Use mcp library directly to verify connection, bypassing ADK Agent complexity
        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed, skipping integration test")

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    tools_result = await session.list_tools()
                    # list_tools returns ListToolsResult, which has 'tools' attribute (list[Tool])
                    tools = tools_result.tools
                    
                    print(f"[Test] Found {len(tools)} tools.")
                    for t in tools:
                        print(f"  - {t.name}")
                    
                    # Assert we found standard Notion tools
                    tool_names = [t.name for t in tools]
                    assert "notion_query_database" in tool_names or "query_database" in tool_names \
                        or any("query" in t for t in tool_names) or "API-post-search" in tool_names
                    
        except Exception as e:
            pytest.fail(f"Failed to connect to MCP server: {e}")

    # Run the async logic in a new event loop
    asyncio.run(_test_logic())

def test_fetch_task_database():
    """
    Integration test to verify we can query the Task Database.
    """
    async def _test_logic():
        toolset = get_notion_mcp_tool()
        params = toolset._connection_params
        server_params = params.server_params
        task_db_id = NOTION_TASK_DATABASE_ID

        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        print(f"\n[Test] Querying Task DB: {task_db_id}")
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Try querying the database
                    result = await session.call_tool(
                        name="API-query-data-source",
                        arguments={
                            "data_source_id": task_db_id,
                            "page_size": 1
                        }
                    )
                    
                    if hasattr(result, 'content') and result.content:
                         text_content = result.content[0].text
                         import json
                         data = json.loads(text_content)
                         
                         if "object" in data and data["object"] == "error":
                             print(f"[Test] Error querying Task DB: {data.get('message')}")
                             # Don't fail the test if it's just permission, but warn
                             pytest.fail(f"Task DB Query Error: {data.get('message')}")
                         
                         results = data.get("results", [])
                         print(f"[Test] Successfully fetched {len(results)} tasks.")
                         if len(results) > 0:
                             print(f"[Test] Sample Task: {results[0].get('url')}")
                    else:
                        pytest.fail(f"Empty response from Task DB query: {result}")

        except Exception as e:
            pytest.fail(f"Exception querying Task DB: {e}")

    asyncio.run(_test_logic())

def test_fetch_project_database():
    """
    Integration test to verify we can query the Project Database.
    """
    async def _test_logic():
        toolset = get_notion_mcp_tool()
        params = toolset._connection_params
        server_params = params.server_params
        project_db_id = NOTION_PROJECT_DATABASE_ID

        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        print(f"\n[Test] Querying Project DB: {project_db_id}")
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    result = await session.call_tool(
                        name="API-query-data-source",
                        arguments={
                            "data_source_id": project_db_id,
                            "page_size": 1
                        }
                    )
                    
                    if hasattr(result, 'content') and result.content:
                         text_content = result.content[0].text
                         import json
                         data = json.loads(text_content)
                         
                         if "object" in data and data["object"] == "error":
                             print(f"[Test] Error querying Project DB: {data.get('message')}")
                             pytest.fail(f"Project DB Query Error: {data.get('message')}")
                         
                         results = data.get("results", [])
                         print(f"[Test] Successfully fetched {len(results)} projects.")
                         if len(results) > 0:
                             print(f"[Test] Sample Project: {results[0].get('url')}")
                    else:
                        pytest.fail(f"Empty response from Project DB query: {result}")

        except Exception as e:
            pytest.fail(f"Exception querying Project DB: {e}")

    asyncio.run(_test_logic())

def test_list_accessible_databases():
    """
    Integration test to list accessible databases and verify permissions.
    """
    async def _test_logic():
        toolset = get_notion_mcp_tool()
        params = toolset._connection_params
        server_params = params.server_params
        
        task_db_id = NOTION_TASK_DATABASE_ID
        
        print(f"\n[Test] Checking access. Target Task DB ID: {task_db_id}")
        
        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    
                    # Use API-post-search to see what's available
                    print("[Test] Searching for accessible databases...")
                    result = await session.call_tool(
                        name="API-post-search",
                        arguments={
                            "page_size": 10
                        }
                    )
                    
                    if hasattr(result, 'content') and result.content:
                         text_content = result.content[0].text
                         import json
                         data = json.loads(text_content)
                         
                         results = data.get("results", [])
                         print(f"[Test] Found {len(results)} accessible databases.")
                         
                         found_ids = []
                         for item in results:
                             db_id = item.get("id").replace("-", "")
                             title = "Unknown"
                             # Try to get title safely
                             try:
                                 title = item.get("title", [{}])[0].get("plain_text", "Untitled")
                             except:
                                 pass
                             
                             print(f"  - DB: {title} (ID: {item.get('id')})")
                             found_ids.append(db_id)
                         
                         # Check if our target is in the list (comparing sans dashes)
                         target_clean = task_db_id.replace("-", "")
                         if target_clean in found_ids:
                             print("[Test] SUCCESS: Target Task Database is accessible.")
                         else:
                             print(f"[Test] WARNING: Target Task Database ({task_db_id}) NOT found in search results.")
                             print("[Test] Please ensure you have shared the database with the integration connection.")
                             
                    else:
                        print(f"[Test] Unexpected search result: {result}")

        except Exception as e:
            pytest.fail(f"Failed to search databases: {e}")

    asyncio.run(_test_logic())

# ============================================================================
# 备忘录（Memo）数据库 CRUD 集成测试
#
# 【如何找到正确的 Notion Database ID】
# -------------------------------------------------------
# Notion 数据库有两类 ID 需要区分，容易混淆：
#
#   1. 页面 URL 中的 ID（正确的 Database ID）：
#      URL 格式：https://www.notion.so/workspace-name/<ID>?v=...
#      例：https://www.notion.so/soc-zxy/3120d59debb7808da582d4baae4fe44b?v=...
#      正确 DB ID = "3120d59d-ebb7-808d-a582-d4baae4fe44b"（URL 路径中的那段）
#
#   2. ?v= 之后的是 View ID，不是 Database ID，不要混用！
#
#   3. API-post-search 返回的 备忘录(ID: xxx) 有时是子页面 ID，
#      也可能与真正的 Database ID 不同，以浏览器地址栏 URL 为准。
#
#   4. 验证方法：直接 POST /v1/pages 到该 ID，成功则确认是正确的 Database ID。
#      （见 test_memo_database_write 写测试）
#
# 最终确认的正确备忘录 Database ID：
#   3120d59d-ebb7-808d-a582-d4baae4fe44b
# ============================================================================

MEMO_DB_ID = NOTION_MEMO_DATABASE_ID


def test_memo_database_write():
    """
    集成测试：向备忘录（Memo）数据库写入一条新记录（Write）。
    验证 API-post-page 可正常往正确的 Database ID 插入数据。
    """
    async def _test_logic():
        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        toolset = get_notion_mcp_tool()
        server_params = toolset._connection_params.server_params

        print(f"\n[Test] Writing to Memo DB: {MEMO_DB_ID}")
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    import json
                    result = await session.call_tool(
                        name="API-post-page",
                        arguments={
                            "parent": {"database_id": MEMO_DB_ID},
                            "properties": {
                                "Note": {
                                    "title": [{"text": {"content": "[集成测试] 自动创建的测试备忘"}}]
                                },
                                "State": {
                                    "select": {"name": "未处理"}
                                }
                            }
                        }
                    )

                    if hasattr(result, 'content') and result.content:
                        data = json.loads(result.content[0].text)
                        if data.get("object") == "error":
                            pytest.fail(f"Write failed: {data.get('message')}")
                        page_id = data.get("id")
                        page_url = data.get("url")
                        print(f"[Test] Successfully created memo page: {page_url}")
                        return page_id
                    else:
                        pytest.fail(f"Empty response from write: {result}")
        except Exception as e:
            pytest.fail(f"Exception writing Memo: {e}")

    asyncio.run(_test_logic())


def test_memo_database_read():
    """
    集成测试：向备忘录数据库写入一条记录，然后立即读取它（Write → Read round-trip）。

    注意：Notion MCP 的两套工具使用不同的 ID 空间：
      - API-post-page 的 parent.database_id 使用页面 URL 中的 ID（如 3120d59d-ebb7-808d-a582-d4baae4fe44b）
      - API-query-data-source 的 data_source_id 使用另一个内部 ID（如 3120d59d-ebb7-81d4-9593-000b5ab3a76c）
    因此读取采用"先写入，再用返回的 page_id 读回"的方式来验证读通路，
    最后将测试数据归档清理。
    """
    async def _test_logic():
        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        toolset = get_notion_mcp_tool()
        server_params = toolset._connection_params.server_params

        import json
        print(f"\n[Test] Read test (write-then-retrieve) on Memo DB: {MEMO_DB_ID}")

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Step 1: 写入
                create_res = await session.call_tool(
                    name="API-post-page",
                    arguments={
                        "parent": {"database_id": MEMO_DB_ID},
                        "properties": {
                            "Note": {
                                "title": [{"text": {"content": "[集成测试] 读测试临时备忘"}}]
                            }
                        }
                    }
                )
                assert hasattr(create_res, 'content') and create_res.content
                create_data = json.loads(create_res.content[0].text)
                if create_data.get("object") == "error":
                    pytest.fail(f"Write step failed: {create_data.get('message')}")
                page_id = create_data.get("id")
                print(f"[Test] Created page ID for read test: {page_id}")

                # Step 2: 读取同一条记录
                read_res = await session.call_tool(
                    name="API-retrieve-a-page",
                    arguments={"page_id": page_id}
                )
                assert hasattr(read_res, 'content') and read_res.content
                read_data = json.loads(read_res.content[0].text)
                if read_data.get("object") == "error":
                    pytest.fail(f"Read step failed: {read_data.get('message')}")
                assert read_data.get("id") == page_id
                print(f"[Test] Successfully read back page: {read_data.get('url')}")

                # Step 3: 清理（归档）
                await session.call_tool(
                    name="API-patch-page",
                    arguments={"page_id": page_id, "archived": True}
                )
                print(f"[Test] Cleaned up (archived) page: {page_id}")

    asyncio.run(_test_logic())



def test_memo_database_write_and_delete():
    """
    集成测试：向备忘录数据库写一条记录，再将其归档删除（Write + Delete）。
    验证完整的写入→软删除（archive）生命周期。
    Notion 没有真正的 DELETE 接口，归档（archived=True）等同于"放入回收站"。
    """
    async def _test_logic():
        try:
            from mcp import stdio_client, ClientSession
        except ImportError:
            pytest.skip("mcp module not installed")

        toolset = get_notion_mcp_tool()
        server_params = toolset._connection_params.server_params

        import json
        created_page_id = None

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1. 写入
                print(f"\n[Test] Creating temp memo in DB: {MEMO_DB_ID}")
                create_res = await session.call_tool(
                    name="API-post-page",
                    arguments={
                        "parent": {"database_id": MEMO_DB_ID},
                        "properties": {
                            "Note": {
                                "title": [{"text": {"content": "[集成测试] 待删除的临时备忘"}}]
                            }
                        }
                    }
                )
                if hasattr(create_res, 'content') and create_res.content:
                    create_data = json.loads(create_res.content[0].text)
                    if create_data.get("object") == "error":
                        pytest.fail(f"Create failed: {create_data.get('message')}")
                    created_page_id = create_data.get("id")
                    print(f"[Test] Created page ID: {created_page_id}")
                else:
                    pytest.fail("Empty response from create step")

                assert created_page_id, "No page ID returned from create"

                # 2. 归档删除（Notion 的软删除）
                print(f"[Test] Archiving (deleting) page: {created_page_id}")
                delete_res = await session.call_tool(
                    name="API-patch-page",
                    arguments={
                        "page_id": created_page_id,
                        "archived": True
                    }
                )
                if hasattr(delete_res, 'content') and delete_res.content:
                    delete_data = json.loads(delete_res.content[0].text)
                    if delete_data.get("object") == "error":
                        pytest.fail(f"Archive failed: {delete_data.get('message')}")
                    assert delete_data.get("archived") is True, "Page not archived"
                    print(f"[Test] Successfully archived (deleted) page: {created_page_id}")
                else:
                    pytest.fail("Empty response from archive step")

    asyncio.run(_test_logic())


if __name__ == "__main__":
    # Allow running file directly
    pytest.main([__file__])

