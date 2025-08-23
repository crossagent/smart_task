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
