# Smart Task Agent

This project is a smart task assistant built with a multi-agent architecture.

## Core Interaction Design: Guiding Agent Behavior via `task_schema.json`

The key to a truly "smart" assistant lies not in just executing commands, but in how it communicates. It should know what to ask, when to ask, and when to stay silent. This project achieves this through a configurable "instruction manual" for the agent: `task_schema.json`.

This file defines the "rules of conversation" for task creation. Instead of hard-coding the interaction logic, the agent reads this schema to guide its behavior, making it both intelligent and customizable.

### The Schema's Core Concepts:

1.  **Importance (`importance`):** Defines how critical a piece of information is.
    *   `required`: **Required Field**. The agent **must** obtain this information (e.g., `title`). If missing, it will always ask until it's provided.
    *   `key`: **Key Field**. Important for organization (e.g., `project`, `due_date`). The agent **should** attempt to get this information, but can proceed if the user skips it.
    *   `optional`: **Optional Field**. Nice to have (e.g., `priority`). The agent **will not** proactively ask for this to avoid unnecessary interruptions.

2.  **Strategy (`strategy`):** Dictates *how* the agent should acquire the information for `key` fields.
    *   `infer_then_ask`: **Infer First, Then Ask.** The agent first tries to deduce the value from context (e.g., matching task title to a project in `project_brief.md`). If successful, it presents its finding as a suggestion ("I think this belongs to 'Project X', is that right?"). This reduces the user's cognitive load.
    *   `ask_if_missing`: **Ask Directly.** If the information is missing, the agent asks a direct question ("Is there a deadline for this?").

### Example Workflow:

-   **User:** "Add 'design new login page' to the 'Website Refactor' project."
-   **Agent:**
    1.  Reads `task_schema.json`.
    2.  Extracts `title` (required) and `project` (key).
    3.  Sees `due_date` (key) is missing. Its strategy is `ask_if_missing`.
    4.  Asks: "Got it. Is there a due date for this task?"
    5.  The interaction is minimal and targeted because all `required` fields were met and only the missing `key` field triggered a question.

This design makes the agent a considerate partner, not just a dumb tool. You can easily fine-tune its "personality" by editing the `task_schema.json` file, without touching a single line of code.

## Project Structure

Here is the proposed directory structure incorporating this design:

```
smart_task_app/
├── __init__.py
├── dispatcher_agent.py         # 1. Dispatcher: Recognizes intent (e.g., add_task) and routes to the correct workflow.
|
├── workflows/                  # 2. Workflows: Handle the logic for a specific scenario.
│   ├── __init__.py
│   └── add_task_workflow.py    #    - Orchestrates the add_task flow: reads schema, calls sub-agents, and talks to the user.
|
└── sub_agents/                 # 3. Sub-Agents: Provide specific, atomic capabilities.
    ├── __init__.py
    ├── context_inference_agent.py # - Infers missing info (like project) by reading the memory-bank.
    └── database_agent.py          # - Handles all communication with the external database (e.g., Notion).

memory-bank/                    # 4. Memory Bank: The agent's long-term knowledge and rules.
├── project_brief.md            #    - Knowledge Source: A list of projects for the context_inference_agent.
└── task_schema.json            #    - ✨Behavioral Rules✨: The core instruction manual that dictates the agent's interaction style.
```
