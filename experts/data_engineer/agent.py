import pathlib
from google.adk.agents import Agent
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.tools import BuiltInCodeExecutor

import os
# 1. Configuration & Paths
BASE_DIR = pathlib.Path(__file__).parent.resolve()
# Support Docker mounting via environment variable
SKILLS_PATH = os.getenv("SKILLS_PATH", str(BASE_DIR.parent.parent / "skills" / "smart_task_management"))
SKILLS_DIR = pathlib.Path(SKILLS_PATH)

# 2. Load the Management Skill
try:
    task_skill = load_skill_from_dir(SKILLS_DIR)
except Exception as e:
    # Fallback or logging if skills aren't found at runtime
    print(f"Warning: Skill directory not found at {SKILLS_DIR}: {e}")
    task_skill = None

# 3. Initialize Code Execution Ability
# BuiltInCodeExecutor allows the agent to write and run Python code.
code_tool = BuiltInCodeExecutor()

# 4. Assemble the Toolset
# We combine the skill-based instructions with the tactical code execution tool.
tools = []
if task_skill:
    tools.append(SkillToolset(
        skills=[task_skill],
        additional_tools=[code_tool]
    ))
else:
    tools.append(code_tool)

# 5. Define the Agent
root_agent = Agent(
    name="data_engineer",
    model="gemini-2.0-flash", # High performance for code/data logic
    instruction="""
    你是一个专业的数据工程师专家。
    
    核心职责：
    1. 负责数据底座的构建、ETL 流程的开发以及复杂数据的清洗与转换。
    2. 当遇到复杂的计算或数据处理逻辑时，优先编写 Python 脚本并通过 code_executor 执行。
    3. 遵循 smart_task_management Skill 规范来管理你的任务状态和输出。
    
    工作风格：
    - 严谨：在执行代码前进行充分的逻辑校验。
    - 闭环：确保每个任务都有明确的输出（Artifacts）并提交到 Hub。
    """,
    tools=tools
)
