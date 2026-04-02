from __future__ import annotations

import sqlite3
import os
from typing import Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field

# Constants
DB_PATH = os.getenv("DATABASE_PATH", "smart_task.db")

# Initialize FastMCP server
mcp = FastMCP("Smart Task Hub")

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
def upsert_resource(
    id: str,
    name: str,
    org_role: str,
    dingtalk_id: Optional[str] = None,
    professional_skill: Optional[str] = None,
    weekly_capacity: int = 40,
    status: str = "Available"
) -> str:
    """
    Create or update a Resource (Personnel/执行人).
    Confirmation: 'name' is the human-readable identifier.
    """
    sql = """
    REPLACE INTO resources (id, name, dingtalk_id, professional_skill, org_role, weekly_capacity, status)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (id, name, dingtalk_id, professional_skill, org_role, weekly_capacity, status)
    try:
        execute_mutation(sql, params)
        return f"Resource '{id}' ({name}) upserted successfully."
    except Exception as e:
        return f"Error upserting resource: {str(e)}"

@mcp.tool()
def upsert_project(
    id: str,
    name: str,
    initiator_res_id: str,
    initiator_res_name: str,
    memo_content: str,
    status: str = "Planning",
    receiver_res_id: Optional[str] = None,
    receiver_res_name: Optional[str] = None,
    deadline: Optional[str] = None,
    ai_summary: Optional[str] = None
) -> str:
    """
    Create or update a Project (Inbox/Root/战略项目池).
    Confirmation: 'name', 'initiator_res_name', 'receiver_res_name'.
    """
    sql = """
    REPLACE INTO projects (id, name, status, initiator_res_id, receiver_res_id, deadline, memo_content, ai_summary)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (id, name, status, initiator_res_id, receiver_res_id, deadline, memo_content, ai_summary)
    try:
        execute_mutation(sql, params)
        return f"Project '{id}' ({name}) upserted successfully."
    except Exception as e:
        return f"Error upserting project: {str(e)}"

@mcp.tool()
def upsert_activity(
    id: str,
    name: str,
    owner_res_id: str,
    owner_res_name: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    deadline: Optional[str] = None,
    benefit: Optional[str] = None,
    priority: str = "P1",
    artifact_url: Optional[str] = None,
    status: str = "Active"
) -> str:
    """
    Create or update an Activity (Execution Path/Strategy/执行活动).
    Confirmation: 'name', 'owner_res_name', 'project_name'.
    """
    sql = """
    REPLACE INTO activities (id, name, project_id, owner_res_id, deadline, benefit, priority, artifact_url, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (id, name, project_id, owner_res_id, deadline, benefit, priority, artifact_url, status)
    try:
        execute_mutation(sql, params)
        return f"Activity '{id}' ({name}) upserted successfully."
    except Exception as e:
        return f"Error upserting activity: {str(e)}"

@mcp.tool()
def upsert_module(
    id: str,
    name: str,
    owner_res_id: str,
    owner_res_name: str,
    parent_module_id: Optional[str] = None,
    parent_module_name: Optional[str] = None,
    knowledge_base: Optional[str] = None,
    layer_type: Optional[str] = None,
    entity_type: str = "Code",
    status: str = "Active"
) -> str:
    """
    Create or update a Module (Physical Asset/Component Tree/物理实体).
    Confirmation: 'name', 'owner_res_name', 'parent_module_name'.
    """
    sql = """
    REPLACE INTO modules (id, name, parent_module_id, owner_res_id, knowledge_base, layer_type, entity_type, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (id, name, parent_module_id, owner_res_id, knowledge_base, layer_type, entity_type, status)
    try:
        execute_mutation(sql, params)
        return f"Module '{id}' ({name}) upserted successfully."
    except Exception as e:
        return f"Error upserting module: {str(e)}"

@mcp.tool()
def upsert_task(
    id: str,
    module_id: str,
    module_name: str,
    resource_id: str,
    resource_name: str,
    module_iteration_goal: str,
    project_id: Optional[str] = None,
    project_name: Optional[str] = None,
    activity_id: Optional[str] = None,
    activity_name: Optional[str] = None,
    estimated_days: float = 0.0,
    status: str = "Todo",
    depends_on: str = "{}",
    start_date: Optional[str] = None,
    due_date: Optional[str] = None,
    artifact_url: Optional[str] = None,
    redmine_id: Optional[str] = None
) -> str:
    """
    Create or update a Task (Atomic Participant/最小执行粒子).
    Confirmation: 'module_name', 'resource_name', 'project_name', 'activity_name'.
    """
    sql = """
    REPLACE INTO tasks (
        id, project_id, activity_id, module_id, resource_id, 
        module_iteration_goal, estimated_days, status, depends_on, 
        start_date, due_date, artifact_url, redmine_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        id, project_id, activity_id, module_id, resource_id, 
        module_iteration_goal, estimated_days, status, depends_on, 
        start_date, due_date, artifact_url, redmine_id
    )
    try:
        execute_mutation(sql, params)
        return f"Task '{id}' upserted successfully."
    except Exception as e:
        return f"Error upserting task: {str(e)}"

# ---------------------------------------------------------------------------
# Deletion Tools (Requiring Confirmation)
# ---------------------------------------------------------------------------

@mcp.tool()
def delete_task(id: str, task_goal_confirmation: str) -> str:
    """Delete a task by ID. Requires human-readable goal confirmation."""
    try:
        count = execute_mutation("DELETE FROM tasks WHERE id = ?", (id,))
        return f"Deleted {count} task(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting task: {str(e)}"

@mcp.tool()
def delete_activity(id: str, activity_name_confirmation: str) -> str:
    """Delete an activity by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM activities WHERE id = ?", (id,))
        return f"Deleted {count} activity/activities with ID '{id}'."
    except Exception as e:
        return f"Error deleting activity: {str(e)}"

@mcp.tool()
def delete_project(id: str, project_name_confirmation: str) -> str:
    """Delete a project by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM projects WHERE id = ?", (id,))
        return f"Deleted {count} project(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting project: {str(e)}"

@mcp.tool()
def delete_module(id: str, module_name_confirmation: str) -> str:
    """Delete a module by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM modules WHERE id = ?", (id,))
        return f"Deleted {count} module(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting module: {str(e)}"

@mcp.tool()
def delete_resource(id: str, resource_name_confirmation: str) -> str:
    """Delete a resource by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM resources WHERE id = ?", (id,))
        return f"Deleted {count} resource(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting resource: {str(e)}"

if __name__ == "__main__":
    import argparse
    
    # Allow transport selection via environment variable or command line
    default_transport = os.getenv("MCP_TRANSPORT", "stdio")
    default_port = int(os.getenv("PORT", "45666"))
    
    parser = argparse.ArgumentParser(description="Run the Smart Task MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "sse"], 
        default=default_transport,
        help=f"Transport to use (default: {default_transport})"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=default_port,
        help=f"Port for SSE transport (default: {default_port})"
    )
    
    args = parser.parse_args()
    
    if args.transport == "sse":
        mcp.run(transport="http", host="0.0.0.0", port=args.port)
    else:
        mcp.run(transport="stdio")
