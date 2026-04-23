"""
Resource Flow and Lifecycle Integration Test Suite.

Tests how resources (Agents) are reserved, heartbeat-monitored, and released 
within the system control bus.
"""

import pytest
import respx
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.scheduler import run_system_bus_cycle
from src.supervisor import agent_supervisor
from src.db import execute_query, execute_mutation


# ==============================================================================
#  FIXTURES
# ==============================================================================
SLICE_SQL = Path(__file__).parent.parent / "fixtures" / "test_slice.sql"


@pytest.fixture(autouse=True)
def seed_test_slice(db_conn):
    sql = SLICE_SQL.read_text(encoding="utf-8")
    cur = db_conn.cursor()
    cur.execute(sql)
    db_conn.commit()
    cur.close()
    yield


@pytest.fixture
def mock_agent_pool():
    original_pool = agent_supervisor.pool
    agent_supervisor.pool = {
        "RES-ARCHITECT-001": {"url": "http://pm:9010",    "agent_id": "pm-agent"},
        "RES-CODER-001": {"url": "http://coder1:9001", "agent_id": "coder-agent-1"},
        "RES-CODER-002": {"url": "http://coder2:9002", "agent_id": "coder-agent-2"},
        "RES-CODER-003": {"url": "http://coder3:9003", "agent_id": "coder-agent-3"},
    }
    with respx.mock(assert_all_called=False):
        respx.post(url__regex=r"http://.*:900\d/.*").respond(200, json={"status": "ok"})
        yield agent_supervisor.pool
    agent_supervisor.pool = original_pool


def run_step():
    with patch("src.scheduler.threading.Thread") as mock_thread:
        def sync_run(target, args=(), kwargs={}, daemon=True):
            target(*args, **kwargs)
            return MagicMock()
        mock_thread.side_effect = sync_run
        run_system_bus_cycle()


def q(sql, params=None):
    return execute_query(sql, params) if params else execute_query(sql)


def resource_available(res_id):
    rows = q("SELECT is_available FROM resources WHERE id = %s", (res_id,))
    return rows[0]['is_available'] if rows else None


# ==============================================================================
#  TESTS
# ==============================================================================
class TestResourceLifecycle:
    """Verify resource state transitions during the bus cycle."""

    @respx.mock
    def test_resource_becomes_busy_on_dispatch(self, mock_agent_pool):
        """When a task is dispatched, the resource must be marked as NOT available."""
        execute_mutation("UPDATE tasks SET status = 'ready' WHERE id = 'TSK-READY-001'")
        execute_mutation("UPDATE system_state SET value = '\"auto\"' WHERE key = 'run_mode'")
        
        respx.post(url__regex=r".*coder3.*sessions$").respond(201)
        respx.post(url__regex=r".*coder3.*/run$").respond(200, json={"status": "ok"})
        
        run_step()
        assert resource_available('RES-CODER-003') is False

    @respx.mock
    def test_resource_released_on_completion(self, mock_agent_pool):
        """When a task reaches a terminal status, the resource must be released."""
        # RES-CODER-002 is busy with TSK-RUN-001 in seed data
        assert resource_available('RES-CODER-002') is False
        
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'TSK-RUN-001'")
        run_step()
        assert resource_available('RES-CODER-002') is True

    @respx.mock
    def test_resource_released_on_failure(self, mock_agent_pool):
        """Even on failure, the resource slot must be freed."""
        execute_mutation("UPDATE tasks SET status = 'failed' WHERE id = 'TSK-RUN-001'")
        run_step()
        assert resource_available('RES-CODER-002') is True

    @respx.mock
    def test_resource_released_on_blocker(self, mock_agent_pool):
        """Even on blocker, the resource slot must be freed."""
        execute_mutation("UPDATE tasks SET status = 'blocked' WHERE id = 'TSK-RUN-001'")
        run_step()
        assert resource_available('RES-CODER-002') is True
