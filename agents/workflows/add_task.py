from google.adk.agents import SequentialAgent
from ..agents.intake import IntakeRouter
from ..agents.scanner import SchemaScanner
from ..agents.inference.orchestrator import InferenceOrchestrator
from ..agents.clarification import ClarificationSynthesizer
from ..agents.fulfillment import Fulfillment

class AddTaskWorkflow(SequentialAgent):
    """
    Sequential workflow for adding a task.
    """
    def __init__(self, name: str = "AddTaskWorkflow"):
        super().__init__(
            name=name,
            sub_agents=[
                IntakeRouter(name="IntakeRouter"),
                SchemaScanner(name="SchemaScanner"),
                InferenceOrchestrator(name="InferenceOrchestrator"),
                ClarificationSynthesizer(name="ClarificationSynthesizer"),
                Fulfillment(name="Fulfillment")
            ]
        )
