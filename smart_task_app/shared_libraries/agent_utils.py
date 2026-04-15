from __future__ import annotations
import os
import subprocess

def execute_shell(command: str) -> str:
    """Executes a shell command. Runs in SMART_WORKSPACE_PATH if set."""
    try:
        cwd = os.getenv("SMART_WORKSPACE_PATH", os.getcwd())
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=60, cwd=cwd
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)
