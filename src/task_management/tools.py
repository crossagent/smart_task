import json
from typing import Optional
from mcp.server.fastmcp import FastMCP
from .db import execute_query, execute_mutation, CustomEncoder

def query_sql(query: str) -> str:
    """
    Execute a raw read-only SQL query against the smart_task PostgreSQL database.
    Use this tool to explore the schema and data.
    Returns JSON-formatted results.
    """
    upper_query = query.strip().upper()
    if any(upper_query.startswith(verb) for verb in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"]):
        return "Error: Only read-only queries (SELECT) are allowed via query_sql."
    
    try:
        results = execute_query(query)
        if not results:
            return "Query executed successfully, but returned no rows."
        return json.dumps(results, indent=2, cls=CustomEncoder, ensure_ascii=False)
    except Exception as e:
        return f"Error executing query: {str(e)}"

def get_database_schema() -> str:
    """
    Retrieve the structure (schema) of all tables in the smart_task database.
    """
    query = """
    SELECT table_name, column_name, data_type, character_maximum_length, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """
    try:
        results = execute_query(query)
        if not results:
            return "No schema information found."
        
        schema = {}
        for row in results:
            table = row['table_name']
            if table not in schema:
                schema[table] = []
            schema[table].append({
                "column": row['column_name'],
                "type": row['data_type'],
                "nullable": row['is_nullable']
            })
        
        return json.dumps(schema, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"Error fetching schema: {str(e)}"

def get_task_context(task_id: str) -> str:
    """
    Retrieve the full context for a given Task, including its parent Activity and Project details.
    """
    query = """
        SELECT 
            t.id as task_id, t.module_iteration_goal, t.status as task_status, t.depends_on,
            m.id as module_id, m.name as module_name, m.knowledge_base,
            a.id as activity_id, a.name as activity_name, a.benefit as activity_benefit,
            p.id as project_id, p.name as project_name, p.memo_content as project_memo
        FROM tasks t
        LEFT JOIN modules m ON t.module_id = m.id
        LEFT JOIN activities a ON t.activity_id = a.id
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE t.id = %s
    """
    try:
        results = execute_query(query, (task_id,))
        if not results:
            return f"Error: Task '{task_id}' not found."
        return json.dumps(results[0], indent=2, ensure_ascii=False, cls=CustomEncoder)
    except Exception as e:
        return f"Database Error: {str(e)}"

def upsert_resource(
    id: str,
    name: str,
    org_role: str,
    resource_type: str = "agent",
    agent_dir: Optional[str] = None,
    workspace_path: Optional[str] = None,
    is_available: bool = True,
    dingtalk_id: Optional[str] = None,
    company_name: Optional[str] = None,
    weekly_capacity: int = 40,
    email: Optional[str] = None
) -> str:
    """
    Create or update a record in the resources table.
    Resources now primarily represent physical assets/compute slots (Agents/Machines).
    """
    sql = """
        INSERT INTO resources (id, name, org_role, dingtalk_id, company_name, 
                             weekly_capacity, email, resource_type, agent_dir, 
                             workspace_path, is_available)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            org_role = EXCLUDED.org_role,
            dingtalk_id = EXCLUDED.dingtalk_id,
            company_name = EXCLUDED.company_name,
            weekly_capacity = EXCLUDED.weekly_capacity,
            email = EXCLUDED.email,
            resource_type = EXCLUDED.resource_type,
            agent_dir = EXCLUDED.agent_dir,
            workspace_path = EXCLUDED.workspace_path,
            is_available = EXCLUDED.is_available,
            updated_at = CURRENT_TIMESTAMP
    """
    try:
        count = execute_mutation(sql, (
            id, name, org_role, dingtalk_id, company_name, weekly_capacity, email,
            resource_type, agent_dir, workspace_path, is_available
        ))
        action = "Inserted" if count == 1 else "Saved (no changes) or Updated"
        return f"Successfully processed resource '{name}' (ID: {id})."
    except Exception as e:
        return f"Error saving resource: {str(e)}"

def upsert_project(
    id: str,
    name: str,
    owner_res_id: str,
    priority: int = 1,
    status: str = "pending",
    memo_content: Optional[str] = None
) -> str:
    """Create or update a record in the projects table."""
    sql = """
        INSERT INTO projects (id, name, owner_res_id, priority, status, memo_content)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            owner_res_id = EXCLUDED.owner_res_id,
            priority = EXCLUDED.priority,
            status = EXCLUDED.status,
            memo_content = EXCLUDED.memo_content,
            updated_at = CURRENT_TIMESTAMP
    """
    try:
        execute_mutation(sql, (id, name, owner_res_id, priority, status, memo_content))
        return f"Successfully processed project '{name}' (ID: {id})."
    except Exception as e:
        return f"Error saving project: {str(e)}"

def upsert_activity(
    id: str,
    project_id: str,
    name: str,
    owner_res_id: str,
    status: str = "pending",
    benefit: Optional[str] = None
) -> str:
    """Create or update a record in the activities table."""
    sql = """
        INSERT INTO activities (id, project_id, name, owner_res_id, status, benefit)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            name = EXCLUDED.name,
            owner_res_id = EXCLUDED.owner_res_id,
            status = EXCLUDED.status,
            benefit = EXCLUDED.benefit,
            updated_at = CURRENT_TIMESTAMP
    """
    try:
        execute_mutation(sql, (id, project_id, name, owner_res_id, status, benefit))
        return f"Successfully processed activity '{name}' (ID: {id})."
    except Exception as e:
        return f"Error saving activity: {str(e)}"

def upsert_module(
    id: str,
    project_id: str,
    name: str,
    owner_res_id: str,
    knowledge_base: Optional[str] = None
) -> str:
    """Create or update a record in the modules table."""
    sql = """
        INSERT INTO modules (id, project_id, name, owner_res_id, knowledge_base)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            project_id = EXCLUDED.project_id,
            name = EXCLUDED.name,
            owner_res_id = EXCLUDED.owner_res_id,
            knowledge_base = EXCLUDED.knowledge_base,
            updated_at = CURRENT_TIMESTAMP
    """
    try:
        execute_mutation(sql, (id, project_id, name, owner_res_id, knowledge_base))
        return f"Successfully processed module '{name}' (ID: {id})."
    except Exception as e:
        return f"Error saving module: {str(e)}"

def upsert_task(
    id: str,
    module_id: str,
    module_name: str,
    resource_id: str,
    resource_name: str,
    module_iteration_goal: str,
    estimated_hours: Optional[float] = None,
    activity_id: Optional[str] = None,
    project_id: Optional[str] = None,
    activity_benefit: Optional[str] = None,
    depends_on: Optional[str] = None,
    status: str = "pending"
) -> str:
    """Create or update a record in the tasks table."""
    sql = """
        INSERT INTO tasks (
            id, module_id, module_name, resource_id, resource_name, 
            module_iteration_goal, estimated_hours, activity_id, project_id, 
            activity_benefit, depends_on, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            module_id = EXCLUDED.module_id,
            module_name = EXCLUDED.module_name,
            resource_id = EXCLUDED.resource_id,
            resource_name = EXCLUDED.resource_name,
            module_iteration_goal = EXCLUDED.module_iteration_goal,
            estimated_hours = EXCLUDED.estimated_hours,
            activity_id = EXCLUDED.activity_id,
            project_id = EXCLUDED.project_id,
            activity_benefit = EXCLUDED.activity_benefit,
            depends_on = EXCLUDED.depends_on,
            status = EXCLUDED.status,
            updated_at = CURRENT_TIMESTAMP
    """
    try:
        execute_mutation(sql, (
            id, module_id, module_name, resource_id, resource_name,
            module_iteration_goal, estimated_hours, activity_id, project_id,
            activity_benefit, depends_on, status
        ))
        return f"Successfully processed task (ID: {id})."
    except Exception as e:
        return f"Error saving task: {str(e)}"

def get_task_logs(task_id: str) -> str:
    """
    Retrieve the execution logs (Events) for a given Task ID.
    Since Agents run asynchronously and persist their turns to the database, 
    this tool allows viewing the reasoning and tool calls of the Agent in real-time.
    """
    query = """
    SELECT author, timestamp, content
    FROM events
    WHERE session_id = %s
    ORDER BY timestamp ASC
    """
    try:
        results = execute_query(query, (task_id,))
        if not results:
            return f"No events found for task '{task_id}'. It might not have started yet (Check if agents are pointed to the shared DB)."
        
        output = []
        for row in results:
            timestamp = row['timestamp']
            if isinstance(timestamp, (int, float)): # Handle cases where it might be a float timestamp
                from datetime import datetime
                timestamp = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(timestamp, 'strftime'):
                timestamp = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            author = row['author']
            content = row['content']
            
            # ADK content is usually a dict. We want to extract the message text.
            if isinstance(content, dict):
                # Try to extract message parts
                parts = content.get('parts', [])
                extracted_text = " ".join([p.get('text', '') for p in parts if isinstance(p, dict)])
                if not extracted_text:
                    extracted_text = str(content)
            else:
                extracted_text = str(content)

            output.append(f"[{timestamp}] {author}: {extracted_text}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Database Error: {str(e)} (Ensure Agents have initialized the events table)"

def delete_record(table: str, id: str) -> str:
    """Delete a record by ID from a specified table."""
    allowed_tables = {"resources", "projects", "activities", "modules", "tasks"}
    if table not in allowed_tables:
        return f"Error: Deletion from table '{table}' is not permitted."
    
    sql = f"DELETE FROM {table} WHERE id = %s"
    try:
        count = execute_mutation(sql, (id,))
        if count == 0:
            return f"Warning: No record found with ID '{id}' in table '{table}'."
        return f"Deleted {count} record(s) from '{table}' with ID '{id}'."
    except Exception as e:
        return f"Error deleting record: {str(e)}"

def report_blocker(task_id: str, reason: str) -> str:
    """
    Report a blocker or failure for a task. 
    Use this tool when encountering API failures, deadlocks, or unresolvable dependencies.
    It marks the task as 'failed' and logs the blocker reason for the human to review.
    """
    sql = "UPDATE tasks SET status = 'failed', blocker_reason = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
    try:
        execute_mutation(sql, (reason, task_id))
        return f"Successfully reported blocker for task {task_id}. The system has registered the issue."
    except Exception as e:
        return f"Error reporting blocker: {str(e)}"

def get_activity_schedule_report(activity_id: str) -> str:
    """
    Generates a human-readable hierarchical Markdown report of the task schedule and status 
    for a given Activity. It visualizes the plan, ETA, and any current blockers.
    """
    try:
        activity_query = "SELECT name, status, priority FROM activities WHERE id = %s"
        acts = execute_query(activity_query, (activity_id,))
        if not acts: return f"Activity {activity_id} not found."
        act = acts[0]

        # Get Modules progress
        prog_query = "SELECT completion_percentage FROM v_activity_progress WHERE activity_id = %s"
        prog = execute_query(prog_query, (activity_id,))
        completion = prog[0]['completion_percentage'] if prog else 0

        # Get Tasks
        tasks_query = """
            SELECT m.name as module_name, t.id, t.module_iteration_goal, t.estimated_hours, t.status, t.blocker_reason
            FROM tasks t
            JOIN modules m ON t.module_id = m.id
            WHERE t.activity_id = %s
            ORDER BY m.name ASC, t.created_at ASC
        """
        tasks = execute_query(tasks_query, (activity_id,))

        status_emoji = {
            'pending': '⏳',
            'ready': '🔵',
            'in_progress': '🔄',
            'code_done': '🧑‍💻',
            'done': '🟢',
            'failed': '🔴',
            'blocked': '🚫',
            'needs_human_help': '🆘'
        }

        report = [f"# Activity: {act['name']} ({act['priority']})"]
        report.append(f"**Status**: {act['status']}")
        report.append(f"**Completion**: {completion}%")
        report.append("\n## Schedule & Tasks")

        total_hours = 0
        from collections import defaultdict
        modules_dict = defaultdict(list)
        for t in tasks:
            modules_dict[t['module_name']].append(t)
            if t['estimated_hours']:
                total_hours += float(t['estimated_hours'])
        
        report.append(f"**Estimated Total Effort**: {total_hours} hours\n")

        for mod_name, m_tasks in modules_dict.items():
            report.append(f"### 📦 Module: {mod_name}")
            for t in m_tasks:
                emoji = status_emoji.get(t['status'], '❓')
                hrs = f"{t['estimated_hours']}h" if t['estimated_hours'] else "N/A"
                report.append(f"- {emoji} **[{t['status'].upper()}]** {t['module_iteration_goal']} (ID: `{t['id']}`, ETA: {hrs})")
                if t['blocker_reason'] and t['status'] in ['failed', 'blocked', 'needs_human_help']:
                    report.append(f"  > **🚨 Blocker**: {t['blocker_reason']}")
            report.append("")

        return "\n".join(report)
    except Exception as e:
        return f"Error generating schedule report: {str(e)}"

def register_tools(mcp: FastMCP):
    """Registers all CRUD database tools to the FastMCP server."""
    mcp.tool()(query_sql)
    mcp.tool()(get_database_schema)
    mcp.tool()(get_task_context)
    mcp.tool()(upsert_resource)
    mcp.tool()(upsert_project)
    mcp.tool()(upsert_activity)
    mcp.tool()(upsert_module)
    mcp.tool()(upsert_task)
    mcp.tool()(delete_record)
    mcp.tool()(get_task_logs)
    mcp.tool()(report_blocker)
    mcp.tool()(get_activity_schedule_report)
