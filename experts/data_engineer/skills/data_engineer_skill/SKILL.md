---
name: smart-task
description: Manage complex engineering tasks, milestones, and system state using the Smart Task Hub. Detects ready tasks, manages DAG dependencies, and coordinates blueprint changes.
version: 1.0.0
---

# Smart Task Management

This skill provides a structured workflow for managing engineering progress within the Smart Task Hub. It leverages MCP tools to interact with a centralized task database and event bus.

## Core Workflow

### 1. Detect & Plan
Identify the current state of the engineering threads and plan the next steps.
- Use `get_database_schema` to understand the current structure if needed.
- Use `query_sql` to fetch active activities and their current task status.
- Use `upsert_milestone` to define high-level checkpoints for an activity.

### 2. Task Promotion
The system handles DAG progression automatically, but you should monitor for "ready" tasks.
- Periodically check for tasks with `status='ready'`.
- Use `get_task_context` to understand the requirements and physical location of a ready task.

### 3. Execution & Assignment
Coordinate the assignment of tasks to available resources.
- Use `assign_task` to link a `ready` task to a resource (compute slot).
- Once a task is assigned, it moves to `in_progress`.

### 4. Reconciliation
Process completed work and trigger the next cycle.
- When work is finished, use `submit_task_deliverable` to record the result.
- If significant architectural changes are needed, use `propose_blueprint_plan` to stage modifications for human approval.
- Use `execute_approved_plan` once a plan is approved by the user.

## Best Practices
- **Atomic Changes**: Keep blueprint modifications focused and well-documented.
- **Milestone Centric**: Always align tasks with defined milestones to track progress effectively.
- **Event Awareness**: Use the event bus (via SQL queries on `events`) to debug state transitions.
