from __future__ import annotations

import os
import subprocess
import threading
import logging
from typing import Optional, Dict, Any, Callable
from src.task_management.db import execute_mutation

logger = logging.getLogger("smart_task.resource_management.supervisor")

class AgentHandle:
    """
    Represents a running agent instance and provides monitoring/control.
    """
    def __init__(self, task_id: str, resource_id: str, process: Optional[subprocess.Popen] = None):
        self.task_id = task_id
        self.resource_id = resource_id
        self.process = process
        self._on_complete_callbacks = []

    def on_complete(self, callback: Callable[[AgentHandle], None]):
        self._on_complete_callbacks.append(callback)

    def wait(self):
        if self.process:
            self.process.wait()
            self._trigger_complete()

    def abort(self):
        if self.process and self.process.poll() is None:
            logger.warning(f"Aborting agent for task {self.task_id} on {self.resource_id}")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self._trigger_complete()

    def _trigger_complete(self):
        for cb in self._on_complete_callbacks:
            try:
                cb(self)
            except Exception as e:
                logger.error(f"Error in on_complete callback: {e}")

class AgentSupervisor:
    """
    Responsible for launching agents and supervising their lifecycle.
    """
    def __init__(self):
        self.active_agents: Dict[str, AgentHandle] = {} # task_id -> Handle

    def dispatch(self, task_id: str, resource_id: str, agent_dir: str, workspace_path: str) -> AgentHandle:
        """
        Launches an agent and returns a handle for monitoring.
        """
        logger.info(f"Dispatching task {task_id} to resource {resource_id}")
        
        # 1. Prepare environment
        env = os.environ.copy()
        env['SMART_TASK_ID'] = task_id
        if workspace_path:
            env['SMART_WORKSPACE_PATH'] = workspace_path
        
        handle = AgentHandle(task_id, resource_id)
        self.active_agents[task_id] = handle

        # 2. Kick off execution in a separate thread
        thread = threading.Thread(
            target=self._run_execution,
            args=(handle, agent_dir, env),
            daemon=True
        )
        thread.start()
        
        return handle

    def _run_execution(self, handle: AgentHandle, agent_dir: str, env: dict):
        """Internal runner that manages the subprocess and callbacks."""
        task_id = handle.task_id
        res_id = handle.resource_id
        
        try:
            # If no agent_dir, mock execution
            if not agent_dir:
                logger.info(f"No agent_dir for {res_id}, mocking execution for 5s...")
                import time
                time.sleep(5)
                # Success by default for mocks
                execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = %s", (task_id,))
            else:
                logger.debug(f"Spawning ADK agent from {agent_dir} for task {task_id}")
                cmd = ["uv", "run", "adk", "run", agent_dir]
                
                process = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                handle.process = process
                
                # Stream logs
                for line in process.stdout:
                    # In a real system, we might push this to a log service or SSE
                    logger.info(f"[{res_id}] {line.strip()}")
                
                process.wait()
                
                if process.returncode != 0:
                    execute_mutation("UPDATE tasks SET status = 'failed' WHERE id = %s", (task_id,))
                    logger.error(f"Task {task_id} failed with exit code {process.returncode}")
                else:
                    # Default success update if agent didn't handle it
                    execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = %s AND status = 'in_progress'", (task_id,))
                    logger.info(f"Task {task_id} completed successfully.")

        except Exception as e:
            logger.error(f"Supervisor error for task {task_id}: {e}")
            execute_mutation("UPDATE tasks SET status = 'failed' WHERE id = %s", (task_id,))
        finally:
            self._cleanup(task_id)
            handle._trigger_complete()

    def _cleanup(self, task_id: str):
        if task_id in self.active_agents:
            del self.active_agents[task_id]
            logger.debug(f"Cleaned up supervisor state for task {task_id}")

# Singleton instance
agent_supervisor = AgentSupervisor()
