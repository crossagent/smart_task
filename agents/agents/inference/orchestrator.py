from google.adk.agents import ParallelAgent
from .project import ProjectSuggester
from .time import DueDateEstimator
from .priority import PrioritySuggester

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
