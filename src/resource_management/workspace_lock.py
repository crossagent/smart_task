from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Set, Dict, Optional

logger = logging.getLogger("smart_task.resource_management.workspace_lock")

LOCK_FILE_NAME = ".smart_task.lock"

class WorkspaceLockManager:
    """
    Manages exclusive access to physical workspace directories.
    Uses an in-memory registry and physical .smart_task.lock files for robustness.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WorkspaceLockManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._active_locks: Dict[str, str] = {}  # Normalized Path -> Task ID
        self._initialized = True
        logger.info("WorkspaceLockManager initialized.")

    def _normalize_path(self, path: str) -> str:
        """Returns the absolute, normalized string representation of a path."""
        return str(Path(path).resolve())

    def try_lock(self, workspace_path: str, task_id: str) -> bool:
        """
        Attempts to acquire an exclusive lock on the given workspace path.
        Returns True if successful, False if already locked.
        """
        if not workspace_path:
            return True # No path, no lock needed
            
        norm_path = self._normalize_path(workspace_path)
        
        # 1. Check in-memory lock
        if norm_path in self._active_locks:
            if self._active_locks[norm_path] == task_id:
                return True # Re-entrant lock for same task
            logger.warning(f"Workspace {norm_path} is already locked in-memory by task {self._active_locks[norm_path]}")
            return False

        # 2. Check physical lock file
        lock_file_path = Path(norm_path) / LOCK_FILE_NAME
        if lock_file_path.exists():
            try:
                content = lock_file_path.read_text().strip()
                logger.warning(f"Workspace {norm_path} has a physical lock file from task {content}")
                # We update in-memory state to reflect physical reality
                self._active_locks[norm_path] = content
                if content != task_id:
                  return False
            except Exception as e:
                logger.error(f"Failed to read lock file at {lock_file_path}: {e}")
                return False

        # 3. Create lock
        try:
            if not Path(norm_path).exists():
                logger.error(f"Workspace path does not exist: {norm_path}")
                return False
                
            lock_file_path.write_text(task_id)
            self._active_locks[norm_path] = task_id
            logger.info(f"Locked workspace {norm_path} for task {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create lock at {norm_path}: {e}")
            return False

    def is_locked(self, workspace_path: str) -> bool:
        """Returns True if the path is currently locked."""
        if not workspace_path:
            return False
        norm_path = self._normalize_path(workspace_path)
        return norm_path in self._active_locks

    def unlock(self, workspace_path: str):
        """Releases the lock on the workspace path."""
        if not workspace_path:
            return
            
        norm_path = self._normalize_path(workspace_path)
        
        # Remove physical lock file
        lock_file_path = Path(norm_path) / LOCK_FILE_NAME
        if lock_file_path.exists():
            try:
                lock_file_path.unlink()
                logger.info(f"Removed physical lock file at {norm_path}")
            except Exception as e:
                logger.error(f"Failed to delete lock file at {lock_file_path}: {e}")

        # Remove from memory
        if norm_path in self._active_locks:
            del self._active_locks[norm_path]
            logger.info(f"Released in-memory lock for {norm_path}")

    def scan_for_existing_locks(self, base_dirs: list[str]):
        """
        Scans a list of base directories for any existing .smart_task.lock files
        to recover the lock state after a crash/restart.
        """
        for base in base_dirs:
            if not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                if LOCK_FILE_NAME in files:
                    full_path = Path(root)
                    norm_path = self._normalize_path(str(full_path))
                    try:
                        task_id = (full_path / LOCK_FILE_NAME).read_text().strip()
                        self._active_locks[norm_path] = task_id
                        logger.info(f"Recovered lock for {norm_path} (Task: {task_id})")
                    except Exception as e:
                        logger.error(f"Failed to recover lock at {norm_path}: {e}")

# Singleton instance
workspace_lock_manager = WorkspaceLockManager()
