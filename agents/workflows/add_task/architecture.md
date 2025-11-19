```mermaid
graph TD
    A["User Input: add task"] --> B["agent_name：IntakeRouter<br>prompt：读取本轮用户输入并确认意图为 add_task"]

    B --> C["agent_name：SchemaScanner<br>prompt：合并历史上下文与本轮新增字段，重新计算缺失列表<br>tools：字段规则表（task_schema.json：字段清单、必填策略、合法值范围）"]
    C --> D{"agent_name：SchemaScanner<br>prompt：更新后的字段集合是否仍缺少必填或关键项？"}

    D -->|Yes| E["agent_name：InferenceOrchestrator<br>prompt：为每个缺失字段生成推断任务并并行调度子 agent<br>tools：字段规则表（task_schema.json：字段清单、策略、合法值）"]

    subgraph ParallelInference["并行子 Agent"]
        direction TB
        E --> P["agent_name：ProjectSuggester<br>prompt：结合项目知识库猜测所属项目及匹配理由<br>tools：项目知识库（project_brief.md：项目背景、别名、 owner）"]
        E --> Q["agent_name：DueDateEstimator<br>prompt：依据 schema 中的日期策略与任务语义推测候选截止日期<br>tools：字段规则表（task_schema.json：due_date 格式与 ask_if_missing 策略提示）"]
        E --> R["agent_name：PrioritySuggester<br>prompt：根据字段规则里的优先级可选项与默认权重给出建议<br>tools：字段规则表（task_schema.json：priority 合法值 + 默认值）"]
    end

    P --> F
    Q --> F
    R --> F

    F["agent_name：ClarificationSynthesizer<br>prompt：汇总各子 agent 候选值并组织成统一的澄清/追问消息模板<br>tools：字段规则表（task_schema.json）"]
    F --> G["agent_name：ConversationEmitter<br>prompt：输出澄清/追问内容（例如：&quot;这属于 Project X 吗？&quot;）并结束本轮<br>tools：字段规则表（task_schema.json）"]
    G --> L["round 结束，等待下一次用户输入（由聊天循环处理）"]

    D -->|No| J["agent_name：FulfillmentPrechecker<br>prompt：确认信息齐全并准备落库<br>tools：字段规则表（task_schema.json）"]
    J --> K["agent_name：TaskWriter<br>prompt：调用外部数据库创建任务记录<br>tools：External DB Client"]
    K --> L
```

### Agent 中文说明

**agent_name：AddTaskAgent**  
prompt：解析 add task 指令，基于 task_schema.json 判断缺失字段，选择推断或追问策略，与用户进行最少打扰的澄清后，将完整任务提交到外部数据库。  
tools：
- 字段规则表（`memory-bank/task_schema.json`）：提供字段清单、合法值范围、必填/策略标记，驱动缺失检测与提示生成。
- 项目知识库（`memory-bank/project_brief.md`）：给出项目背景与别名，方便推断关联项目等上下文。
- 外部任务写入器（`External DB Client`）：负责将整理好的任务同步到 Notion 等外部数据库。

**子 Agent 角色速览**
- `InferenceOrchestrator`：根据缺失字段生成推断任务，并把它们广播给并行子 agent。
- `ProjectSuggester / DueDateEstimator / PrioritySuggester`：各自调用对应知识来源，输出字段候选值与置信度说明。
- `ClarificationSynthesizer`：负责汇总候选值、标记仍需追问的字段，并产出统一的对话提示。
