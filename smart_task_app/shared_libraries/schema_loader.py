from __future__ import annotations
import json
import os
from google.adk.agents.callback_context import CallbackContext

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logseq_schema.json")

async def load_logseq_schema_callback(callback_context: CallbackContext):
    """
    Load the Logseq 5-Database schema from the central JSON artifact 
    and inject it into the context state for the agent to reference in its prompt.
    """
    if not os.path.exists(SCHEMA_PATH):
        callback_context.state["logseq_schema"] = "Logseq Schema artifact not found."
        return

    try:
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            # Flatten or summarize the schema for the prompt
            summary = "Logseq 5-Database Schema (Atomic State Machine Engine):\n"
            summary += f"Rule: {schema.get('modification_rule')}\n"
            for class_name, class_info in schema.get('classes', {}).items():
                props = class_info.get('properties', {})
                prop_str = ", ".join([f"{k}: {v}" for k, v in props.items()])
                summary += f"- {class_name} ({class_info['role']}): {prop_str}\n"
            
            callback_context.state["logseq_schema"] = summary
    except Exception as e:
        callback_context.state["logseq_schema"] = f"Error loading schema: {str(e)}"
