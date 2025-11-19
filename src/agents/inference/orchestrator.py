from google.adk.agents import ParallelAgent
from src.agents.inference.project import ProjectSuggester
from src.agents.inference.time import DueDateEstimator
from src.agents.inference.priority import PrioritySuggester

class InferenceOrchestrator(ParallelAgent):
    """
    Orchestrator that runs inference agents in parallel.
    """
    def __init__(self, name: str = "InferenceOrchestrator"):
        super().__init__(
            name=name,
            sub_agents=[
                ProjectSuggester(name="ProjectSuggester"),
                DueDateEstimator(name="DueDateEstimator"),
                PrioritySuggester(name="PrioritySuggester")
            ]
        )
