from __future__ import annotations
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

def execute_shell(command: str) -> str:
    """Executes a shell command. Runs in SMART_WORKSPACE_PATH if set."""
    try:
        cwd = os.getenv("SMART_WORKSPACE_PATH", os.getcwd())
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=120, cwd=cwd
        )
        return f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return str(e)

def sync_agent_workspace() -> str:
    """
    Ensures the local workspace is up-to-date with the remote main branch.
    Uses git pull --rebase to maintain a clean history and handle simple conflicts.
    """
    try:
        cwd = os.getenv("AGENT_BASE_PATH", os.getcwd())
        # Try to pull with rebase
        result = subprocess.run(
            ["git", "pull", "origin", "main", "--rebase"],
            capture_output=True, text=True, cwd=cwd, timeout=60
        )
        if result.returncode == 0:
            return "Workspace synchronized successfully via git pull --rebase."
        else:
            # If rebase fails, it might need manual intervention, but we try to abort
            subprocess.run(["git", "rebase", "--abort"], cwd=cwd)
            return f"Git Sync Failed:\n{result.stderr}"
    except Exception as e:
        return f"Git Sync Exception: {str(e)}"

def dispatch_agent_deliverables(commit_message: str = "Agent update") -> str:
    """
    Commits all local changes and pushes them to the remote main branch.
    Handles potential push conflicts by pulling again before pushing.
    """
    try:
        cwd = os.getenv("AGENT_BASE_PATH", os.getcwd())
        
        # 1. Add and Commit
        subprocess.run(["git", "add", "."], cwd=cwd, check=True)
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=cwd)
        if not status.stdout.strip():
            return "No changes to dispatch."
            
        subprocess.run(["git", "commit", "-m", commit_message], cwd=cwd, check=True)
        
        # 2. Push with retry logic for conflicts
        for attempt in range(3):
            push_res = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True, cwd=cwd)
            if push_res.returncode == 0:
                return f"Deliverables dispatched successfully: {commit_message}"
            
            # If push failed, try to pull-rebase and retry
            logger.warning(f"Push failed (attempt {attempt+1}), attempting rebase: {push_res.stderr}")
            sync_res = sync_agent_workspace()
            if "failed" in sync_res.lower():
                return f"Push failed and rebase cleanup failed: {sync_res}"
        
        return "Failed to dispatch deliverables after 3 attempts due to persistent conflicts."
    except Exception as e:
        return f"Dispatch Exception: {str(e)}"
