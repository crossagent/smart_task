from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class TaskState:
    """
    Global state object passed between agents in the Add Task workflow.
    """
    user_input: str = ""
    parsed_fields: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    
    # Candidates suggested by inference agents
    # Format: { "field_name": "suggested_value" }
    inference_candidates: Dict[str, str] = field(default_factory=dict)
    
    # Questions generated for clarification
    clarification_questions: List[str] = field(default_factory=list)
    
    # The final task object ready for database insertion
    final_task: Optional[Dict[str, Any]] = None
    
    # Conversation history for context
    history: List[Dict[str, str]] = field(default_factory=list)
