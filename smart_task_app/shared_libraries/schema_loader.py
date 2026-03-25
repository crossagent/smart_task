from __future__ import annotations
import json
import os
from google.adk.agents.callback_context import CallbackContext

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "notion_schema.json")

async def load_notion_schema_callback(callback_context: CallbackContext):
    """
    Load the Notion 5-Database schema from the central JSON artifact 
    and inject it into the context state for the agent to reference in its prompt.
    """
    if not os.path.exists(SCHEMA_PATH):
        callback_context.state["notion_schema"] = "Schema artifact not found."
        return

    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            # Flatten or summarize the schema for the prompt
            summary = "Notion 5-Database Schema & Relational Rules:\n"
            summary += f"Modification Rule: {schema.get('modification_rule')}\n"
            for db_name, db_info in schema.get('databases', {}).items():
                summary += f"- {db_name} ({db_info['role']}): {', '.join(db_info['properties'])}\n"
            
            callback_context.state["notion_schema"] = summary
    except Exception as e:
        callback_context.state["notion_schema"] = f"Error loading schema: {str(e)}"
