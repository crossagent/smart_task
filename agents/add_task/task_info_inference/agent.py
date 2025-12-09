from typing import AsyncGenerator
from google.adk.agents import BaseAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from .project import ProjectSuggester
from .time import DueDateEstimator
from .priority import PrioritySuggester


class InferenceOrchestrator(BaseAgent):
    """
    条件编排器 (Custom Agent) - 只有在有缺失字段时才执行并行推断
    
    这是一个合理的Custom Agent使用场景,因为需要自定义条件逻辑:
    - 检查scan_result中是否有缺失字段
    - 如果有缺失字段,运行并行推断agents
    - 如果没有缺失字段,跳过推断
    """
    
    # Pydantic字段声明
    parallel_inference: ParallelAgent
    
    # 允许任意类型(ADK agents不是标准Python类型)
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, name: str = "InferenceOrchestrator"):
        """
        初始化InferenceOrchestrator
        
        创建内部的ParallelAgent用于并行推断
        """
        # 创建并行推断agent
        parallel_inference = ParallelAgent(
            name="ParallelInference",
            sub_agents=[
                ProjectSuggester(),
                DueDateEstimator(),
                PrioritySuggester()
            ]
        )
        
        # 调用父类初始化,传递所有字段
        super().__init__(
            name=name,
            parallel_inference=parallel_inference,
            sub_agents=[parallel_inference]  # sub_agents用于框架跟踪
        )
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        条件执行逻辑:
        1. 检查是否有缺失字段
        2. 如果有,执行并行推断
        3. 如果没有,跳过推断
        """
        # 检查是否有缺失字段
        scan_result = ctx.session.state.get("scan_result", {})
        missing_fields = scan_result.get("missing_fields", [])
        all_fields_present = scan_result.get("all_fields_present", False)
        
        if all_fields_present or not missing_fields:
            # 没有缺失字段,跳过推断
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(
                    text="所有必填字段都已齐全,跳过推断阶段。"
                )])
            )
            return
        
        # 有缺失字段,执行并行推断
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(
                text=f"发现缺失字段: {missing_fields},开始并行推断..."
            )])
        )
        
        # 执行并行推断agents (现在可以安全地访问self.parallel_inference)
        async for event in self.parallel_inference._run_async_impl(ctx):
            yield event
        
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(
                text="并行推断完成。"
            )])
        )


inference_orchestrator = InferenceOrchestrator()
