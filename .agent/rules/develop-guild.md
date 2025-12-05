---
trigger: always_on
---

## 4. 评估与测试 (Evaluation & Testing)

评估是保证 Agent 智能程度和稳定性的关键环节。我们采用分层评估策略。

### 4.1 单元测试 (Unit Eval) - 针对单个 Agent
**目标**: 验证单个 Agent 在特定输入下是否能输出预期的结果（JSON 结构、字段值等）。

*   **方法**: 为每个 Agent 编写独立的 `.evalset.json` 测试集。
*   **运行命令**:
    ```bash
    adk eval agents/agents/inference/priority.py tests/priority.evalset.json
    ```
*   **关注点**:
    *   Prompt 是否能引导模型输出正确的 JSON 格式？
    *   在边界情况下（如信息不足），Agent 是否能正确返回 "unknown" 或默认值？

### 4.2 集成测试 (Integration Eval) - 针对完整工作流
**目标**: 验证 `AddTaskWorkflow` 从用户输入到最终执行的完整链路。

*   **方法**: 编写包含多轮对话的 `.evalset.json`。
*   **运行命令**:
    ```bash
    adk eval agents/workflows/add_task.py tests/workflow.evalset.json
    ```
*   **关注点**:
    *   Agent 之间的状态传递是否正确（如 `scan_result` 是否正确传递给了 `InferenceOrchestrator`）？
    *   条件执行逻辑是否生效（如字段齐全时是否跳过了推断阶段）？

### 4.3 评估技巧 (Eval Tips)

#### 使用 Rubrics 进行模糊匹配
对于自然语言生成的内容（如澄清问题），不要使用精确字符串匹配。使用 ADK 的 **Rubric** 功能，让 LLM 作为裁判来打分。

**示例配置 (`eval_config.json`)**:
```json
{
  "criteria": {
    "rubric_based_tool_use_quality_v1": {
      "threshold": 1.0,
      "rubrics": [
        {
          "rubricId": "check_clarification",
          "rubricContent": {
            "textProperty": "The response should politely ask for the missing 'due_date'."
          }
        }
      ]
    }
  }
}
```

#### 调试 Trace
使用 `adk web` 查看详细的执行 Trace，这对于理解多 Agent 协作中的数据流向非常有帮助。

```bash
adk web .
```

## 5. 常用命令速查

*   **启动 Web 调试界面**: `adk web .`
*   **运行 CLI 交互**: `adk run .`
*   **运行评估**: `adk eval <agent_path> <evalset_path>`