import os
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


# Eager initialization
notion_token = os.environ.get("NOTION_TOKEN")
if not notion_token:
    # Fallback to NOTION_API_KEY for backward compatibility
    notion_token = os.environ.get("NOTION_API_KEY")

if not notion_token:
    # We raise an error immediately on import if token is missing,
    # unless we want to allow import but fail on usage?
    # User requested "startup initialization", implying fail-fast is desired.
    raise ValueError("NOTION_TOKEN environment variable is not set. Please adding it to .env file.")

_NOTION_MCP_TOOL = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@notionhq/notion-mcp-server",
            ],
            env={
                "NOTION_TOKEN": notion_token,
            }
        ),
        timeout=30,
    ),
)


def get_notion_mcp_tool() -> McpToolset:
    """
    Returns the pre-initialized Notion MCP Toolset.
    """
    return _NOTION_MCP_TOOL


