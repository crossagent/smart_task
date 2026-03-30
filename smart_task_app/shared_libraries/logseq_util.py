from __future__ import annotations

import os
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


# Eager initialization for Logseq (DB version)
logseq_api_token = os.environ.get("LOGSEQ_API_TOKEN")
logseq_api_url = os.environ.get("LOGSEQ_API_URL", "http://localhost:12315")

if not logseq_api_token:
    # Fail-fast as per user's "atomization" and "automated governance" requirements.
    # The system cannot function without a valid connection to the local graph.
    raise ValueError(
        "LOGSEQ_API_TOKEN environment variable is not set. "
        "Please enable Logseq HTTP API and add the token to your .env file."
    )

# MCP Toolset for Logseq (2026 stable community version)
_LOGSEQ_MCP_TOOL = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--with",
                "mcp-logseq",
                "mcp-logseq",
            ],
            env={
                "LOGSEQ_API_TOKEN": logseq_api_token,
                "LOGSEQ_API_URL": logseq_api_url,
            }
        ),
        timeout=30,
    ),
)


def get_logseq_mcp_tool() -> McpToolset:
    """
    Returns the pre-initialized Logseq MCP Toolset.
    """
    return _LOGSEQ_MCP_TOOL
