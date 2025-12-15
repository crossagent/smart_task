from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

# Import sub-agents
from .granularity.agent import GranularityAdvisor
from .scanner import SchemaScanner
from .task_info_inference import InferenceOrchestrator as InfoInferenceOrchestrator
from .clarification import ClarificationSynthesizer
from .fulfillment import Fulfillment


class AddTaskWorkflow(BaseAgent):
    """
    AddTaskWorkflow - 动态根编排器 (Dynamic Root Orchestrator)
    
    职责:
    - 作为 Add Task 工作流的唯一入口
    - 显式管理生命周期: 意图分析 -> 缺失扫描 -> 并行推断 -> 澄清提问 -> 执行
    - 支持多轮对话中的"暂停与恢复"
    """
    
    # Sub-agents
    advisor: BaseAgent
    scanner: BaseAgent
    inference: BaseAgent
    clarification: BaseAgent
    fulfillment: BaseAgent
    
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(self, name: str = "AddTaskWorkflow"):
        # Instantiate sub-agents
        advisor = GranularityAdvisor()
        scanner = SchemaScanner()
        inference = InfoInferenceOrchestrator()
        clarification = ClarificationSynthesizer()
        fulfillment = Fulfillment()
        
        super().__init__(
            name=name,
            advisor=advisor,
            scanner=scanner,
            inference=inference,
            clarification=clarification,
            fulfillment=fulfillment,
            sub_agents=[advisor, scanner, inference, clarification, fulfillment]
        )
        self.advisor = advisor
        self.scanner = scanner
        self.inference = inference
        self.clarification = clarification
        self.fulfillment = fulfillment
        
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # =========================================================
        # Phase 1: Granularity Analysis & Intake (Always Run)
        # =========================================================
        # 即使是第二轮对话，我们也重新分析，以捕捉用户"改变主意"或"纠正意图"的情况
        async for event in self.advisor.run(ctx):
            yield event
            
        granularity_result = ctx.session.state.get("granularity_result")
        if not granularity_result:
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text="Error: Analysis failed.")]))
            return

        decision = granularity_result.get("decision")
        confidence = granularity_result.get("confidence", 0.0)
        clarification_q = granularity_result.get("clarification_question")

        # 将分析出的 title/type/granularity 注入到 basic_info 以供后续流程使用
        # SchemaScanner 和 Inference 依赖 basic_info
        ctx.session.state["basic_info"] = {
            "title": granularity_result.get("title", ""),
            "type": granularity_result.get("type", "task"),
            "raw_input": ctx.session.state.get("user_input", "") 
        }
        ctx.session.state["granularity"] = decision

        # 阈值检查: 如果意图模糊，直接提问并返回
        if decision == "AMBIGUOUS" or confidence < 0.8:
            question = clarification_q if clarification_q else "Could you clarify if this is a Project or Task?"
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text=question)]))
            # STOP EXECUTION: 等待用户下一轮输入
            return

        # =========================================================
        # Phase 2: Schema Scanning (Missing Fields)
        # =========================================================
        # 根据确定的 Granularity 扫描缺失字段
        async for event in self.scanner.run(ctx):
            yield event
            
        # =========================================================
        # Phase 3: Inference (Fill Missing)
        # =========================================================
        # 尝试使用各种推断 Agent 填充缺失字段
        async for event in self.inference.run(ctx):
            yield event
            
        # =========================================================
        # Phase 4: Clarification check
        # =========================================================
        # 综合当前所有信息，判断是否还需要问用户
        async for event in self.clarification.run(ctx):
            yield event
            
        clarification_state = ctx.session.state.get("clarification", {})
        if clarification_state.get("needs_clarification"):
            question = clarification_state.get("question")
            yield Event(author=self.name, content=types.Content(parts=[types.Part(text=question)]))
            # STOP EXECUTION: 等待用户补充信息
            return

        # =========================================================
        # Phase 5: Fulfillment (Execution)
        # =========================================================
        # 信息已完备，执行写入
        async for event in self.fulfillment.run(ctx):
            yield event


add_task_agent = AddTaskWorkflow()
