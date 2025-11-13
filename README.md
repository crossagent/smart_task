# Smart Task Agent

This project is a smart task assistant built with a multi-agent architecture.

## Project Structure

Here is the proposed directory structure for the agents:

```
agents/
├── __init__.py
├── dispatcher_agent.py         # 1. Dispatcher Agent: Handles intent recognition and workflow dispatching.
|
├── workflows/                  # 2. Workflows: Handle specific multi-step tasks.
│   ├── __init__.py
│   ├── add_task_workflow.py    #    - Workflow for adding tasks, handles multi-turn conversations.
│   └── list_tasks_workflow.py  #    - Workflow for listing tasks.
|
└── sub_agents/                 # 3. Sub-Agents: Atomic capability agents that can be used as tools within workflows.
    ├── __init__.py
    ├── chat_reader_agent.py    #    - Agent for reading information from chat groups.
    └── permission_manager_agent.py #    - Agent for handling permissions.
```


思考：
1.研究-执行，根据执行结果调整的循环
2.研究主要是逐渐明确任务的复杂度和归属
3.聚合页面的展示和初始的任务记录是两码事
4.根据意图选择工作流，工作流来保证风险步骤都有人类确认