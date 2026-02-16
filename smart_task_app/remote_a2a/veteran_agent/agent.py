# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from google.genai import types
from vertexai.preview import rag
from dotenv import load_dotenv
from smart_task_app.shared_libraries.constants import MODEL
from .tools.update_plan import update_plan, STRATEGIC_PLAN_KEY
from typing import Optional

load_dotenv()


def inject_plan_to_instruction(callback_context: CallbackContext) -> Optional[types.Content]:
    """
    Before agent callback that ensures plan state is available for template replacement.
    
    CRITICAL: ADK will automatically replace {{strategic_plan}} in the instruction with
    the value from state[STRATEGIC_PLAN_KEY]. If the key is missing, ADK will raise
    KeyError: 'Context variable not found: strategic_plan'.
    
    This callback ensures the key always exists in state with a default value.
    
    Args:
        callback_context: CallbackContext with access to state
        
    Returns:
        None to allow normal execution
    """
    # IMPORTANT: Modify state using the state object, not the dict
    # Get current state - this returns a read-only view
    current_state = callback_context.state.to_dict()
    
    # Check if plan exists
    if STRATEGIC_PLAN_KEY not in current_state or not current_state.get(STRATEGIC_PLAN_KEY):
        # Set default value in state so ADK template replacement works
        # Use callback_context.state to set values (not the dict)
        callback_context.state[STRATEGIC_PLAN_KEY] = ""
        print(f"[VeteranAgent] No plan in state - set default empty value")
    else:
        current_plan = current_state.get(STRATEGIC_PLAN_KEY, "")
        print(f"[VeteranAgent] Plan exists in state: {len(current_plan)} chars")
    
    # Return None to allow normal execution
    # ADK will now successfully replace {{strategic_plan}} with state[STRATEGIC_PLAN_KEY]
    return None


def return_instructions_root() -> str:
    """
    Returns the instruction template for the Veteran Agent.
    
    Uses {{strategic_plan}} placeholder which ADK will automatically replace
    with the value from state[STRATEGIC_PLAN_KEY].
    """
    instruction = """
你是"老兵助手"（Veteran Agent）。你是一个经验丰富的计划管理者，负责：
1. 从历史经验中检索参考方案
2. **维护执行计划（Strategic Plan）**

## 当前执行计划状态

{{strategic_plan}}

---

## 核心工作原则

### 计划优先原则

**如果当前没有计划**（上方显示为空）：
- 你必须首先帮助用户创建一个执行计划
- 步骤：
  1. 理解用户的目标和需求
  2. 使用 `retrieve_rag_documentation` 检索相关的历史案例
  3. 基于检索结果和用户需求，使用 `update_plan` 创建详细计划

**如果已有计划**（上方已显示计划内容）：
- 根据用户的新需求和对话上下文，判断是否需要更新计划
- 更新情况包括：
  - 用户提出新的目标或变更
  - 发现更好的解决方案
  - 遇到障碍需要调整策略
  - 用户明确要求更新计划

### 工作流程（Prompt-Driven）

你的工作流程**完全由对话驱动**：

1. **理解上下文**
   - 查看上方的当前计划状态
   - 理解用户的最新消息
   - 判断用户的意图

2. **决策行动**
   - **没有计划？** → 根据用户目标，检索案例，创建计划
   - **有计划但执行遇到了问题？** → 根据问题进一步检索新信息，更新计划

3. **执行并输出**
   - 使用工具（检索或更新计划）
   - 以 Markdown 格式组织输出
   - 清晰说明你的决策和建议

### 可用工具

1. **retrieve_rag_documentation**: 从历史案例库检索相关经验
   - 输入查询关键词
   - 返回前10个最相关结果
   - 用于：创建计划前的参考、补充计划细节

2. **update_plan**: 更新或创建执行计划
   - 输入：完整的 Markdown 格式计划内容
   - 自动保存到 state 和 artifact
   - 用于：首次创建计划、更新现有计划

### 计划格式要求（Markdown）

计划必须是清晰的 Markdown 格式，包括：

```markdown
# 执行计划：[计划名称]

## 目标
明确的目标描述

## 背景
相关背景信息和历史案例参考

## 主要步骤
1. 第一步：具体描述
2. 第二步：具体描述
3. ...

## 预期结果
明确的成功标准

## 参考案例
- [案例1]: 简要描述
- [案例2]: 简要描述

## 风险和注意事项
- 风险1：应对措施
- 风险2：应对措施
```

## 交互原则

你是作为子 agent 被主 agent 调用的。更新计划时，使用 `update_plan` 工具传入**完整的 Markdown 计划**，不是增量更新。

- 始终使用中文
- 计划要具体、可执行
- 引用历史案例时注明来源和相似度
- 主动询问不明确的信息
- 保持计划的单一来源（strategic_plan.md）
"""
    
    return instruction


# Create RAG retrieval tool
ask_vertex_retrieval = VertexAiRagRetrieval(
    name='retrieve_rag_documentation',
    description=(
        'Use this tool to retrieve documentation and reference materials '
        'for the question from the RAG corpus. This tool searches through '
        'historical cases and reference solutions.'
    ),
    rag_resources=[
        rag.RagResource(
            rag_corpus=os.environ.get("RAG_CORPUS", "")
        )
    ],
    similarity_top_k=10,
    vector_distance_threshold=0.6,
)

root_agent = LlmAgent(
    model=MODEL,
    name='VeteranAgent',
    description='老兵代理：检索历史经验案例并维护执行计划',
    instruction=return_instructions_root(),  # 调用函数返回包含 {{strategic_plan}} 的模板字符串
    before_agent_callback=inject_plan_to_instruction,  # ADK 会自动用 state 替换模板中的占位符
    tools=[
        ask_vertex_retrieval,
        update_plan,
    ]
)
