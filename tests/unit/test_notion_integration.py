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
        task_db_id = os.environ.get("NOTION_TASK_DATABASE_ID")
        
        if not task_db_id:
            pytest.skip("NOTION_TASK_DATABASE_ID not set")

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
        project_db_id = os.environ.get("NOTION_PROJECT_DATABASE_ID")
        
        if not project_db_id:
            pytest.skip("NOTION_PROJECT_DATABASE_ID not set")

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
        
        task_db_id = os.environ.get("NOTION_TASK_DATABASE_ID", "1990d59debb7816dab7bf83e93458d30")
        
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

if __name__ == "__main__":
    # Allow running file directly
    pytest.main([__file__])
