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

"""Update and persist strategic plan using ADK artifacts."""
from __future__ import annotations

import logging
from typing import Any
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)

# State key for strategic plan
STRATEGIC_PLAN_KEY = "strategic_plan"


async def update_plan(tool_context: ToolContext, plan_content: str) -> dict[str, Any]:
  """
  Update the Strategic Plan and persist it as an artifact.
  
  This tool:
  1. Updates the plan in the agent's state
  2. Persists it as a markdown artifact for long-term storage
  3. Makes the plan accessible across sessions
  
  Args:
      tool_context: ADK tool context
      plan_content: Full content of the plan in Markdown format.
                    Should describe tasks, steps, and expected outcomes.
  
  Returns:
      dict with status, message, and plan_length
  """
  # 1. Update State
  state = tool_context.state
  state[STRATEGIC_PLAN_KEY] = plan_content
  
  # 2. Persist to Artifact
  try:
    from google.genai import types
    
    plan_artifact = types.Part.from_bytes(
      data=plan_content.encode('utf-8'),
      mime_type="text/markdown"
    )
    
    metadata = {
      "type": "task",
      "subtype": "strategic_plan"
    }
    
    # Always overwrite to keep single source of truth
    await tool_context.save_artifact(
      filename="strategic_plan.md",
      artifact=plan_artifact,
      custom_metadata=metadata
    )
    
    logger.info(f"Strategic plan updated and saved ({len(plan_content)} chars)")
    return {
      'status': 'ok',
      'message': '计划已成功更新并保存。',
      'plan_length': len(plan_content)
    }
  except Exception as e:
    logger.error(f"Failed to save plan artifact: {e}")
    return {
      'status': 'error',
      'message': f'保存计划失败: {e}'
    }
