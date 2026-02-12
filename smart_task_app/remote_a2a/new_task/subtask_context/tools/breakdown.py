def suggest_breakdown(task_title: str, task_description: str = "") -> str:
    """
    Pure LLM-based suggestion for now, as we don't have a specific 'Subtask Library'.
    This tool might be redundant if the Agent itself (SubtaskContextAgent) uses its own knowledge,
    but we keep it as a placeholder for future 'Template Lookup'.
    
    For now, return a placeholder string that prompts the Agent to generate it.
    """
    return "USE_LLM_KNOWLEDGE_TO_GENERATE_BREAKDOWN"
