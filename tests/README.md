# 测试方案 (Testing Strategy)

本目录包含 BugSleuth 的自动化测试基础设施。

## 测试金字塔 (3-Level Pyramid)

采用渐进式测试策略，从纯代码逻辑到复杂 Agent 推理逐层验证。

### Level 0: 单元测试 (Unit Tests)
- **目标**: 验证独立函数、解析器、工具类
- **位置**: `test/unit/`
- **方法**: 标准 `pytest`，直接函数调用
- **运行时机**: 每次文件保存

### Level 1: 集成测试 (Integration Tests)
- **目标**: 验证 Agent/Tool 工作流。"如果 LLM *想要* 执行 X，系统能正确执行吗？"
- **位置**: `test/integration/`
- **核心组件**:
  - **app_factory**: 统一的应用初始化
  - **MockLlm**: 预定义响应的"脚本化大脑"
  - **TestClient**: 测试客户端，封装 ADK Runner
- **运行时机**: 功能完成 / Pre-commit

### Level 2: 系统测试 (System/Eval Tests)
- **目标**: 评估"智能性"和 Prompt 质量
- **位置**: `eval_cases/`
- **核心**: ADK Eval System，使用真实 LLM
- **运行时机**: 每晚或修改核心 Prompt 时

---

## 目录结构

```
test/
├── conftest.py                 # pytest 配置，自动设置 MockLlm
├── integration/
│   ├── test_bug_analyze_flow.py  # 分析 Agent 测试
│   └── test_bug_sleuth_flow.py   # 完整流程测试
└── unit/
    └── ...
```

---

## 关键组件

### 1. conftest.py

自动在测试开始前设置环境：

```python
def pytest_configure(config):
    # 设置 mock 模型（在任何导入之前）
    os.environ["GOOGLE_GENAI_MODEL"] = "mock/pytest"

@pytest.fixture(scope="session", autouse=True)
def register_mock_llm():
    LLMRegistry.register(MockLlm)

@pytest.fixture(autouse=True)
def reset_mock_behaviors():
    MockLlm.clear_behaviors()
```

### 2. app_factory

统一的应用初始化入口：

```python
from bug_sleuth.app_factory import create_app, AppConfig

app = create_app(AppConfig(
    agent_name="bug_analyze_agent",  # 或 "bug_scene_agent"
))
```

### 3. MockLlm

模拟 LLM 响应：

```python
from bug_sleuth.testing import MockLlm

MockLlm.set_behaviors({
    # 返回文本
    "关键词": {"text": "响应文本"},
    
    # 调用工具
    "关键词": {
        "tool": "tool_name",
        "args": {"param": "value"}
    }
})
```

### 4. TestClient

封装 ADK Runner 的测试客户端：

```python
from bug_sleuth.testing import AgentTestClient

client = TestClient(agent=app.agent, app_name="test_app")
await client.create_new_session("user_1", "sess_1")
responses = await client.chat("用户消息")
```

---

## 运行测试

```bash
# 运行所有集成测试
python -m pytest test/integration/ -v

# 运行特定测试
python -m pytest test/integration/test_bug_analyze_flow.py::test_analyze_agent_searches_logs -v

# 运行单元测试
python -m pytest test/unit/ -v
```

---

## 编写测试步骤

1. **确定测试路径**: "我需要测试 'Agent 调用 git log 工具' 流程"

2. **配置 Mock 行为**:
   ```python
   MockLlm.set_behaviors({
       "check logs": {
           "tool": "get_git_log_tool",
           "args": {"limit": 5}
       }
   })
   ```

3. **创建应用和客户端**:
   ```python
   app = create_app(AppConfig(agent_name="bug_analyze_agent"))
   client = TestClient(agent=app.agent, app_name="test_app")
   ```

4. **执行并验证**:
   ```python
   await client.create_new_session("user_1", "sess_1")
   responses = await client.chat("Please check logs")
   assert "[MockLlm]" in responses[-1]
   ```

---

## 共享 Fixture

```python
@pytest.fixture
def mock_external_deps():
    """只 mock 外部工具检查，使用真实 config.yaml"""
    with patch("...agent.check_search_tools", return_value=None):
        yield
```

---

## 模型选择

测试通过 `conftest.py` 自动使用 MockLlm：

| 场景 | GOOGLE_GENAI_MODEL | 说明 |
|------|-------------------|------|
| 测试 | `mock/pytest` | conftest 自动设置 |
| 生产 | `gemini-3-flash-preview` | 默认值 |
| 多模型 | `openai/gpt-4o` | LiteLLM 包装 |
