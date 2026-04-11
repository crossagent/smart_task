import os
import shutil
import pytest
from pathlib import Path
from src.resource_management.workspace_lock import WorkspaceLockManager, LOCK_FILE_NAME

@pytest.fixture
def temp_workspace(tmp_path):
    """Creates a temporary directory to act as a workspace."""
    d = tmp_path / "test_workspace"
    d.mkdir()
    return str(d)

def test_lock_and_unlock(temp_workspace):
    manager = WorkspaceLockManager()
    # Reset singleton state for testing if needed, 
    # but here we just use it.
    manager._active_locks = {}
    
    task_id = "TSK-001"
    
    # 1. Successful lock
    assert manager.try_lock(temp_workspace, task_id) is True
    assert manager.is_locked(temp_workspace) is True
    assert (Path(temp_workspace) / LOCK_FILE_NAME).exists()
    assert (Path(temp_workspace) / LOCK_FILE_NAME).read_text() == task_id
    
    # 2. Duplicate lock from same task (allowed/idempotent)
    assert manager.try_lock(temp_workspace, task_id) is True
    
    # 3. Conflict lock
    assert manager.try_lock(temp_workspace, "TSK-002") is False
    
    # 4. Unlock
    manager.unlock(temp_workspace)
    assert manager.is_locked(temp_workspace) is False
    assert not (Path(temp_workspace) / LOCK_FILE_NAME).exists()

def test_physical_lock_recovery(temp_workspace):
    manager = WorkspaceLockManager()
    manager._active_locks = {}
    
    task_id = "TSK-RECOVERY"
    lock_file = Path(temp_workspace) / LOCK_FILE_NAME
    lock_file.write_text(task_id)
    
    # Manager should detect the physical lock file even if memory is empty
    assert manager.try_lock(temp_workspace, "TSK-OTHER") is False
    assert manager.try_lock(temp_workspace, task_id) is True
    
def test_scan_for_existing_locks(tmp_path):
    manager = WorkspaceLockManager()
    manager._active_locks = {}
    
    # Setup multiple workspaces with locks
    w1 = tmp_path / "w1"
    w1.mkdir()
    (w1 / LOCK_FILE_NAME).write_text("T1")
    
    w2 = tmp_path / "w2"
    w2.mkdir()
    (w2 / LOCK_FILE_NAME).write_text("T2")
    
    # Scan
    manager.scan_for_existing_locks([str(tmp_path)])
    
    assert manager.is_locked(str(w1)) is True
    assert manager.is_locked(str(w2)) is True
    assert manager._active_locks[str(w1.resolve())] == "T1"

# Add is_locked to WorkspaceLockManager if it's missing (I forgot it in implementation)
