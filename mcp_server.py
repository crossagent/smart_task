from __future__ import annotations

import sqlite3
import os
from typing import Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Constants
DB_PATH = "smart_task.db"

# Initialize FastMCP server
mcp = FastMCP("Smart Task DB Server")

# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

def get_db_connection():
    """Create a new database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def execute_query(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return results as a list of dicts."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def execute_mutation(query: str, params: tuple = ()) -> int:
    """Execute a mutation SQL (INSERT, UPDATE, DELETE) and return the row count."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount

# ---------------------------------------------------------------------------
# Core MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def query_sql(sql: str) -> str:
    """
    Execute a read-only SQL query against the smart_task database.
    Use this for data exploration and reporting.
    """
    if not sql.strip().upper().startswith("SELECT"):
        return "Error: Only SELECT queries are allowed via query_sql. Use execute_sql for mutations."
    
    try:
        results = execute_query(sql)
        if not results:
            return "No results found."
        import json
        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Database Error: {str(e)}"

@mcp.tool()
def execute_sql(sql: str) -> str:
    """
    Execute a mutation SQL command (INSERT, UPDATE, DELETE).
    Handle with care as this modifies the persistent state.
    """
    try:
        count = execute_mutation(sql)
        return f"Success: {count} row(s) affected."
    except Exception as e:
        return f"Database Error: {str(e)}"

@mcp.tool()
def get_db_schema() -> str:
    """
    Retrieve the current database schema, including table names and columns.
    Essential for understanding the available data structures.
    """
    query = "SELECT sql FROM sqlite_master WHERE type='table';"
    try:
        results = execute_query(query)
        schemas = [row["sql"] for row in results if row["sql"]]
        return "\n\n".join(schemas)
    except Exception as e:
        return f"Error fetching schema: {str(e)}"

# ---------------------------------------------------------------------------
# High-Level Entity CRUD Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def upsert_task(
    id: str,
    name: str,
    module_id: str,
    target_state: str,
    resource_id: Optional[str] = None,
    feature_id: Optional[str] = None,
    event_id: Optional[str] = None,
    estimated_hours: float = 0.0,
    status: str = "Todo",
    depends_on: Optional[str] = None,
    due_date: Optional[str] = None
) -> str:
    """
    Create or update a Task.
    Tasks are idempotent state transformations tied to a specific module.
    """
    sql = """
    REPLACE INTO tasks (
        id, name, event_id, feature_id, module_id, resource_id, 
        target_state, estimated_hours, status, depends_on, due_date
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (id, name, event_id, feature_id, module_id, resource_id, target_state, estimated_hours, status, depends_on, due_date)
    try:
        execute_mutation(sql, params)
        return f"Task '{id}' upserted successfully as idempotent state change for module '{module_id}'."
    except Exception as e:
        return f"Error upserting task: {str(e)}"

@mcp.tool()
def upsert_module(
    id: str,
    name: str,
    status: str = "Active",
    owner_id: Optional[str] = None,
    description: str = "",
    type: str = "Technical"
) -> str:
    """Create or update a Module (physical or logical unit of the system)."""
    sql = "REPLACE INTO modules (id, name, status, owner_id, description, type) VALUES (?, ?, ?, ?, ?, ?)"
    params = (id, name, status, owner_id, description, type)
    try:
        execute_mutation(sql, params)
        return f"Module '{id}' upserted successfully."
    except Exception as e:
        return f"Error upserting module: {str(e)}"

@mcp.tool()
def upsert_feature(
    id: str,
    name: str,
    event_id: str,
    status: str = "Planning",
    owner: str = "",
    collaborators: str = ""
) -> str:
    """Create or update a Feature (a cohesive implementation plan)."""
    sql = "REPLACE INTO features (id, name, event_id, status, owner, collaborators) VALUES (?, ?, ?, ?, ?, ?)"
    params = (id, name, event_id, status, owner, collaborators)
    try:
        execute_mutation(sql, params)
        return f"Feature '{id}' upserted successfully."
    except Exception as e:
        return f"Error upserting feature: {str(e)}"

if __name__ == "__main__":
    mcp.run()
