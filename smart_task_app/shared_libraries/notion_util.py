import os
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

# Global singleton instance
_NOTION_MCP_TOOL = None

def get_notion_mcp_tool() -> McpToolset:
    """
    Returns the Notion MCP Toolset configured with the Notion Token from environment variables.
    Maintains a global unique instance.
    """
    global _NOTION_MCP_TOOL
    if _NOTION_MCP_TOOL is not None:
        return _NOTION_MCP_TOOL

    notion_token = os.environ.get("NOTION_TOKEN")
    if not notion_token:
        # Fallback to NOTION_API_KEY if NOTION_TOKEN is not set, for backward compatibility during migration
        notion_token = os.environ.get("NOTION_API_KEY")
    
    if not notion_token:
        raise ValueError("NOTION_TOKEN environment variable is not set.")

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
    return _NOTION_MCP_TOOL

