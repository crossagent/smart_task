import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import Any, Optional
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
import json
from datetime import datetime, date
from decimal import Decimal

class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime, date, and Decimal objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Constants - PostgreSQL Connection
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smart_task_hub")
DB_USER = os.getenv("DB_USER", "smart_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "smart_pass")

def get_db_connection():
    """Create a new PostgreSQL database connection using current environment variables."""
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("DB_NAME", "smart_task_hub")
    # print(f"> [get_db_connection] {host}:{port}/{dbname}")
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=os.getenv("DB_USER", "smart_user"),
        password=os.getenv("DB_PASSWORD", "smart_pass")
    )

def execute_query(query: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a read-only SQL query and return results as a list of dicts."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

def execute_mutation(query: str, params: tuple = ()) -> int:
    """Execute a mutation SQL (INSERT, UPDATE, DELETE) and return the row count."""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount

# ---------------------------------------------------------------------------
# FastMCP Server Initialization
# ---------------------------------------------------------------------------

# Initialize FastMCP server
mcp = FastMCP("Smart Task Hub")


# Define CORS middleware to allow all origins, solving "Permission" issues
# for cross-origin or containerized web-client connections.
mcp_middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

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
        return json.dumps(results, indent=2, ensure_ascii=False, cls=CustomEncoder)
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
    Retrieve the current database schema.
    Essential for understanding the available data structures in PostgreSQL.
    """
    query = """
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """
    try:
        results = execute_query(query)
        if not results:
            return "No schema information found."
        
        output = []
        current_table = ""
        for row in results:
            if row['table_name'] != current_table:
                current_table = row['table_name']
                output.append(f"\nTable: {current_table}")
            output.append(f"  - {row['column_name']} ({row['data_type']})")
        
        return "\n".join(output)
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
    INSERT INTO resources (id, name, dingtalk_id, professional_skill, org_role, weekly_capacity, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        dingtalk_id = EXCLUDED.dingtalk_id,
        professional_skill = EXCLUDED.professional_skill,
        org_role = EXCLUDED.org_role,
        weekly_capacity = EXCLUDED.weekly_capacity,
        status = EXCLUDED.status
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
    INSERT INTO projects (id, name, status, initiator_res_id, receiver_res_id, deadline, memo_content, ai_summary)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        status = EXCLUDED.status,
        initiator_res_id = EXCLUDED.initiator_res_id,
        receiver_res_id = EXCLUDED.receiver_res_id,
        deadline = EXCLUDED.deadline,
        memo_content = EXCLUDED.memo_content,
        ai_summary = EXCLUDED.ai_summary
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
    INSERT INTO activities (id, name, project_id, owner_res_id, deadline, benefit, priority, artifact_url, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        project_id = EXCLUDED.project_id,
        owner_res_id = EXCLUDED.owner_res_id,
        deadline = EXCLUDED.deadline,
        benefit = EXCLUDED.benefit,
        priority = EXCLUDED.priority,
        artifact_url = EXCLUDED.artifact_url,
        status = EXCLUDED.status
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
    INSERT INTO modules (id, name, parent_module_id, owner_res_id, knowledge_base, layer_type, entity_type, status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        parent_module_id = EXCLUDED.parent_module_id,
        owner_res_id = EXCLUDED.owner_res_id,
        knowledge_base = EXCLUDED.knowledge_base,
        layer_type = EXCLUDED.layer_type,
        entity_type = EXCLUDED.entity_type,
        status = EXCLUDED.status
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
    INSERT INTO tasks (
        id, project_id, activity_id, module_id, resource_id, 
        module_iteration_goal, estimated_days, status, depends_on, 
        start_date, due_date, artifact_url, redmine_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        project_id = EXCLUDED.project_id,
        activity_id = EXCLUDED.activity_id,
        module_id = EXCLUDED.module_id,
        resource_id = EXCLUDED.resource_id,
        module_iteration_goal = EXCLUDED.module_iteration_goal,
        estimated_days = EXCLUDED.estimated_days,
        status = EXCLUDED.status,
        depends_on = EXCLUDED.depends_on,
        start_date = EXCLUDED.start_date,
        due_date = EXCLUDED.due_date,
        artifact_url = EXCLUDED.artifact_url,
        redmine_id = EXCLUDED.redmine_id
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
        count = execute_mutation("DELETE FROM tasks WHERE id = %s", (id,))
        return f"Deleted {count} task(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting task: {str(e)}"

@mcp.tool()
def delete_activity(id: str, activity_name_confirmation: str) -> str:
    """Delete an activity by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM activities WHERE id = %s", (id,))
        return f"Deleted {count} activity/activities with ID '{id}'."
    except Exception as e:
        return f"Error deleting activity: {str(e)}"

@mcp.tool()
def delete_project(id: str, project_name_confirmation: str) -> str:
    """Delete a project by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM projects WHERE id = %s", (id,))
        return f"Deleted {count} project(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting project: {str(e)}"

@mcp.tool()
def delete_module(id: str, module_name_confirmation: str) -> str:
    """Delete a module by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM modules WHERE id = %s", (id,))
        return f"Deleted {count} module(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting module: {str(e)}"

@mcp.tool()
def delete_resource(id: str, resource_name_confirmation: str) -> str:
    """Delete a resource by ID. Requires name confirmation."""
    try:
        count = execute_mutation("DELETE FROM resources WHERE id = %s", (id,))
        return f"Deleted {count} resource(s) with ID '{id}'."
    except Exception as e:
        return f"Error deleting resource: {str(e)}"

if __name__ == "__main__":
    import argparse
    
    # Allow transport selection via environment variable or command line
    default_transport = os.getenv("MCP_TRANSPORT", "stdio")
    default_port = int(os.getenv("PORT", "45666"))
    default_host = os.getenv("MCP_HOST", "0.0.0.0") if os.getenv("MCP_TRANSPORT") == "http" else "127.0.0.1"
    
    parser = argparse.ArgumentParser(description="Run the Smart Task MCP Server")
    parser.add_argument(
        "--transport", 
        choices=["stdio", "http"], 
        default=default_transport,
        help=f"Transport to use (default: {default_transport})"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to for HTTP (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=default_port,
        help=f"Port for HTTP (default: {default_port})"
    )
    
    args = parser.parse_args()
    
    if args.transport == "http":
        # FastMCP uses transport="streamable-http" for robust bidirectional streaming
        # Binding to 0.0.0.0 is critical for accessibility from outside Docker
        print(f"Starting Smart Task Hub on {args.host}:{args.port} using streamable-http...")
        mcp.run(
            transport="streamable-http", 
            host=args.host, 
            port=args.port,
            middleware=mcp_middleware
        )
    else:
        mcp.run(transport="stdio")
