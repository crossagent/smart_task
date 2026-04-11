from __future__ import annotations

import os
import subprocess
import threading
import logging
import yaml
import time
import httpx
from typing import Optional, Dict, List, Any, Callable
from src.task_management.db import execute_mutation

logger = logging.getLogger("smart_task.resource_management.supervisor")

class PersistentAgentHandle:
    """
    Represents a long-running Agent API server.
    """
    def __init__(self, agent_id: str, resource_id: str, dir: str, port: int, workspace: str):
        self.agent_id = agent_id
        self.resource_id = resource_id
        self.dir = dir
        self.port = port
        self.workspace = workspace
        self.process: Optional[subprocess.Popen] = None
        self.url = f"http://localhost:{port}"

    def is_alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

class AgentSupervisor:
    """
    Manages a pool of persistent ADK api_server processes.
    """
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.pool: Dict[str, PersistentAgentHandle] = {} # resource_id -> Handle
        self.db_url: str = ""
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def load_config(self):
        """Loads agent pool configuration from config.yaml."""
        if not os.path.exists(self.config_path):
            logger.error(f"Config file not found: {self.config_path}")
            return

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            self.db_url = config.get("db_url", "")
            
            for agent_cfg in config.get("agents_pool", []):
                handle = PersistentAgentHandle(
                    agent_id=agent_cfg["id"],
                    resource_id=agent_cfg["resource_id"],
                    dir=agent_cfg["dir"],
                    port=agent_cfg["port"],
                    workspace=agent_cfg.get("default_workspace", "")
                )
                self.pool[handle.resource_id] = handle

    def bootstrap(self):
        """Starts all persistent agents in the pool."""
        self.load_config()
        logger.info(f"Bootstrapping Agent Pool with {len(self.pool)} agents...")
        
        for handle in self.pool.values():
            self._start_agent_process(handle)

        # 启动自愈和监控守护线程
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()

    def _start_agent_process(self, handle: PersistentAgentHandle):
        """Launches a single adk api_server process."""
        logger.info(f"Starting API server for {handle.agent_id} on port {handle.port}")
        
        # 准备环境变量
        env = os.environ.copy()
        if self.db_url:
            env["SESSION_SERVICE_URI"] = self.db_url
        if handle.workspace:
            env["SMART_WORKSPACE_PATH"] = handle.workspace

        # 命令：uv run adk api_server <dir> --port <port>
        cmd = ["uv", "run", "adk", "api_server", handle.dir, "--port", str(handle.port)]
        
        try:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            handle.process = process
            
            # 日志聚合记录（异步）
            threading.Thread(target=self._log_reader, args=(handle,), daemon=True).start()
            
        except Exception as e:
            logger.error(f"Failed to start agent {handle.agent_id}: {e}")

    def _log_reader(self, handle: PersistentAgentHandle):
        """Reads and logs output from an agent process."""
        prefix = f"[{handle.agent_id}:{handle.port}]"
        if handle.process and handle.process.stdout:
            for line in handle.process.stdout:
                logger.debug(f"{prefix} {line.strip()}")

    def _watchdog_loop(self):
        """Continuously monitors health and restarts failed agents."""
        while not self._stop_event.is_set():
            self._reconcile_pool()
            # 每 10 秒检查一次
            time.sleep(10)

    def _reconcile_pool(self):
        """Internal logic to check health and trigger restarts."""
        for handle in self.pool.values():
            if not handle.is_alive():
                logger.warning(f"Agent {handle.agent_id} (port {handle.port}) died. Restarting...")
                self._start_agent_process(handle)

    def get_agent_url(self, resource_id: str) -> Optional[str]:
        """Returns the HTTP endpoint for the given resource."""
        handle = self.pool.get(resource_id)
        return handle.url if handle else None

    def stop(self):
        """Stops the pool and all processes."""
        self._stop_event.set()
        for handle in self.pool.values():
            if handle.process:
                handle.process.terminate()
        logger.info("Agent Pool stopped.")

# Singleton instance
agent_supervisor = AgentSupervisor()
