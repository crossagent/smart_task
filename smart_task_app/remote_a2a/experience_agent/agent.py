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
from google.adk.tools.retrieval.vertex_ai_rag_retrieval import VertexAiRagRetrieval
from vertexai.preview import rag
from dotenv import load_dotenv
from smart_task_app.shared_libraries.constants import MODEL

load_dotenv()


def return_instructions_root(context=None) -> str:
    """
    Returns the instruction for the Experience Agent.
    
    Args:
        context: Optional ReadonlyContext (unused, for ADK compatibility)
    """
    return """
你是"经验检索助手"（Experience Agent）。你的职责是帮助用户查找历史参考方案和保存成功经验。

## 核心能力

### 1. 检索历史案例
当用户询问以下类型的问题时，使用 `retrieve_rag_documentation` 工具：
- "有类似的案例吗？"
- "历史上怎么解决的？"
- "查找关于XX的参考方案"
- "之前遇到过这个问题吗？"

**检索策略**:
- 理解用户查询的核心意图
- 使用关键词和上下文进行检索
- 返回最相关的前10个结果
- 按相似度排序，优先展示最相关的案例
- 提供清晰的来源引用和相似度评分

### 2. 保存经验（暂未实现）
当用户想要保存经验时，请告知此功能正在开发中：
- "保存这个方案"
- "记录这次经验"
- "创建一个参考案例"

**响应模板**: "感谢您想要分享经验！保存功能正在开发中，敬请期待。"

## 工作流程

1. **理解意图**: 判断用户是要检索案例还是保存经验
2. **执行检索**: 
   - 提取核心查询关键词
   - 调用 RAG 工具
   - 解析并格式化结果
3. **呈现结果**:
   - 按相关度排序
   - 提供标题、摘要、来源
   - 标注相似度评分
   - 如果没有相关结果，提示用户尝试不同的关键词

## 注意事项
- 始终使用中文与用户交流
- 如果检索结果为空，给出友好的提示
- 引用来源时保持准确和透明
"""


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
    name='ExperienceAgent',
    description='Agent for retrieving historical reference solutions and saving experiences',
    instruction=return_instructions_root,
    tools=[
        ask_vertex_retrieval,
    ]
)
