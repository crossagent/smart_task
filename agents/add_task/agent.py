from google.adk.agents import SequentialAgent
from .intake import IntakeRouter
from .scanner import SchemaScanner
from .task_info_inference import InferenceOrchestrator
from .clarification import ClarificationSynthesizer
from .fulfillment import Fulfillment


def AddTaskWorkflow(name: str = "AddTaskWorkflow") -> SequentialAgent:
    """
    AddTask工作流 - 顺序执行的任务创建流程
    
    流程:
    1. IntakeRouter: 从用户输入中提取基本信息
    2. SchemaScanner: 扫描缺失字段
    3. InferenceOrchestrator: 条件执行并行推断(仅在有缺失字段时)
    4. ClarificationSynthesizer: 生成澄清问题
    5. Fulfillment: 完成任务创建或输出澄清问题
    """
    return SequentialAgent(
        name=name,
        description="添加任务的完整工作流",
        sub_agents=[
            IntakeRouter(),
            SchemaScanner(),
            InferenceOrchestrator(),
            ClarificationSynthesizer(),
            Fulfillment()
        ]
    )


add_task_agent = AddTaskWorkflow()
