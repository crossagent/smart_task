"""
Event Bus Cycle Integration Test Suite.

Tests the full 4-phase scheduler cycle (Detect → Consume → Execute → Reconcile)
against a REAL database with MOCKED agent dispatch.

Seed data is loaded from tests/fixtures/test_slice.sql — a designed, repeatable
test slice covering all major scenarios. See that file for the full data dictionary.
"""

import os
import pytest
import respx
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from src.task_execution.scheduler import run_system_bus_cycle
from src.resource_management.supervisor import agent_supervisor
from src.task_management.db import execute_query, execute_mutation, get_db_connection


# ═══════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════

SLICE_SQL = Path(__file__).parent.parent / "fixtures" / "test_slice.sql"


@pytest.fixture(autouse=True)
def seed_test_slice(db_conn):
    """
    Load the test slice SQL before each test.
    This is IDEMPOTENT — it cleans and re-seeds every time.
    """
    sql = SLICE_SQL.read_text(encoding="utf-8")
    cur = db_conn.cursor()
    cur.execute(sql)
    db_conn.commit()
    cur.close()
    yield
    # No cleanup needed — next test will re-seed


@pytest.fixture
def mock_agent_pool():
    """Mock the agent supervisor pool — no real LLM calls."""
    original_pool = agent_supervisor.pool
    agent_supervisor.pool = {
        "RES-PM-001":    {"url": "http://pm:9010",    "agent_id": "pm-agent"},
        "RES-CODER-001": {"url": "http://coder1:9001", "agent_id": "coder-agent-1"},
        "RES-CODER-002": {"url": "http://coder2:9002", "agent_id": "coder-agent-2"},
        "RES-CODER-003": {"url": "http://coder3:9003", "agent_id": "coder-agent-3"},
    }
    yield agent_supervisor.pool
    agent_supervisor.pool = original_pool


# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════

def run_step():
    """Execute a single bus cycle with threading mocked to run synchronously."""
    with patch("src.task_execution.scheduler.threading.Thread") as mock_thread:
        def sync_run(target, args=(), kwargs={}, daemon=True):
            target(*args, **kwargs)
            return MagicMock()
        mock_thread.side_effect = sync_run
        run_system_bus_cycle()


def q(sql, params=None):
    """Shorthand for execute_query."""
    return execute_query(sql, params) if params else execute_query(sql)


def task_status(task_id):
    rows = q("SELECT status FROM tasks WHERE id = %s", (task_id,))
    return rows[0]['status'] if rows else None


def task_exists(task_id):
    return len(q("SELECT id FROM tasks WHERE id = %s", (task_id,))) > 0


def resource_available(res_id):
    rows = q("SELECT is_available FROM resources WHERE id = %s", (res_id,))
    return rows[0]['is_available'] if rows else None


def events_for(task_id=None, event_type=None, status=None):
    """Query events with optional filters."""
    clauses, params = [], []
    if task_id:
        clauses.append("task_id = %s"); params.append(task_id)
    if event_type:
        clauses.append("event_type = %s"); params.append(event_type)
    if status:
        clauses.append("status = %s"); params.append(status)
    where = " AND ".join(clauses)
    sql = f"SELECT * FROM events WHERE {where}" if where else "SELECT * FROM events"
    return q(sql, tuple(params) if params else None)


def count_events(status='pending'):
    rows = q("SELECT COUNT(*) as cnt FROM events WHERE status = %s", (status,))
    return rows[0]['cnt']


# ═══════════════════════════════════════════════════════════════
#  PHASE 1: EVENT DETECTION
# ═══════════════════════════════════════════════════════════════

class TestEventDetection:
    """Verify the Detect phase emits correct events from the test slice."""

    @respx.mock
    def test_initial_state_is_clean(self, mock_agent_pool):
        """Before any cycle, there should be 0 events."""
        assert count_events('pending') == 0

    @respx.mock
    def test_failed_task_detected(self, mock_agent_pool):
        """TSK-FAIL-001 (failed) should produce a task_failed event."""
        run_step()
        evts = events_for(task_id='TSK-FAIL-001', event_type='task_failed')
        assert len(evts) >= 1
        payload = evts[0]['payload'] if isinstance(evts[0]['payload'], dict) else json.loads(evts[0]['payload'])
        assert 'rate limit' in payload['reason'].lower()

    @respx.mock
    def test_blocked_task_detected(self, mock_agent_pool):
        """TSK-BLOCK-001 (blocked) should produce a task_blocked event."""
        run_step()
        evts = events_for(task_id='TSK-BLOCK-001', event_type='task_blocked')
        assert len(evts) >= 1

    @respx.mock
    def test_stalled_activity_detected(self, mock_agent_pool):
        """ACT-STALL-001 (all tasks terminal) should produce activity_stalled event."""
        run_step()
        evts = events_for(event_type='activity_stalled')
        stall_evts = [e for e in evts if e['activity_id'] == 'ACT-STALL-001']
        assert len(stall_evts) >= 1

    @respx.mock
    def test_no_duplicate_events_on_second_cycle(self, mock_agent_pool):
        """Running two cycles should NOT create duplicate pending events."""
        run_step()
        count_after_1 = count_events('pending')
        run_step()
        count_after_2 = count_events('pending')
        # Second cycle should not inflate pending count (dedup index)
        assert count_after_2 <= count_after_1

    @respx.mock
    def test_human_instruction_detected(self, mock_agent_pool):
        """Updating activity instruction should trigger human_instruction event."""
        execute_mutation("""
            UPDATE activities 
            SET user_instruction = 'Prioritize security hardening',
                instruction_version = 1
            WHERE id = 'ACT-LIVE-001'
        """)
        run_step()
        evts = events_for(event_type='human_instruction')
        assert len(evts) >= 1
        assert evts[0]['activity_id'] == 'ACT-LIVE-001'


# ═══════════════════════════════════════════════════════════════
#  PHASE 2: EVENT CONSUMPTION
# ═══════════════════════════════════════════════════════════════

class TestEventConsumption:
    """Verify events are consumed and translated into Task mutations."""

    @respx.mock
    def test_failed_task_creates_repair(self, mock_agent_pool):
        """task_failed event for TSK-FAIL-001 → creates REPAIR-TSK-FAIL-001."""
        run_step()
        assert task_exists('REPAIR-TSK-FAIL-001')
        repair = q("SELECT * FROM tasks WHERE id = 'REPAIR-TSK-FAIL-001'")[0]
        assert repair['resource_id'] == 'RES-PM-001'
        assert repair['status'] == 'ready'
        assert 'INTERRUPT SIGNAL' in repair['module_iteration_goal']

    @respx.mock
    def test_blocked_task_creates_repair(self, mock_agent_pool):
        """task_blocked event for TSK-BLOCK-001 → creates REPAIR-TSK-BLOCK-001."""
        run_step()
        assert task_exists('REPAIR-TSK-BLOCK-001')

    @respx.mock
    def test_stalled_activity_creates_review_task(self, mock_agent_pool):
        """activity_stalled event → creates REV-ACT-STALL-001."""
        run_step()
        assert task_exists('REV-ACT-STALL-001')
        rev = q("SELECT * FROM tasks WHERE id = 'REV-ACT-STALL-001'")[0]
        assert rev['resource_id'] == 'RES-PM-001'
        assert 'Review Activity' in rev['module_iteration_goal']

    @respx.mock
    def test_consumed_event_marked_processing(self, mock_agent_pool):
        """After consumption, events should be 'processing' not 'pending'."""
        run_step()
        evts = events_for(task_id='TSK-FAIL-001')
        statuses = [e['status'] for e in evts]
        assert 'processing' in statuses or 'resolved' in statuses

    @respx.mock
    def test_human_instruction_creates_cmd_task(self, mock_agent_pool):
        """Injected human_instruction event → creates CMD task."""
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, payload)
            VALUES ('human_instruction', 'human', 'critical', 'ACT-LIVE-001',
                    '{"instruction": "Drop everything, fix the auth bug", "version": 99}')
        """)
        run_step()
        assert task_exists('CMD-ACT-LIVE-001-V99')
        cmd = q("SELECT * FROM tasks WHERE id = 'CMD-ACT-LIVE-001-V99'")[0]
        assert 'HUMAN COMMAND' in cmd['module_iteration_goal']


# ═══════════════════════════════════════════════════════════════
#  PHASE 3: DATA PLANE (Promote + Dispatch)
# ═══════════════════════════════════════════════════════════════

class TestDataPlane:
    """Verify task promotion and agent dispatch."""

    @respx.mock
    def test_pending_no_dep_promoted(self, mock_agent_pool):
        """TSK-PEND-002 (pending, no deps) → ready."""
        run_step()
        assert task_status('TSK-PEND-002') == 'ready'

    @respx.mock
    def test_pending_dep_met_promoted(self, mock_agent_pool):
        """TSK-PEND-001 (pending, dep TSK-DONE-001 is done) → ready."""
        run_step()
        assert task_status('TSK-PEND-001') == 'ready'

    @respx.mock
    def test_pending_dep_not_met_stays(self, mock_agent_pool):
        """TSK-PEND-003 (pending, dep TSK-PEND-001 not done) → stays pending."""
        run_step()
        assert task_status('TSK-PEND-003') == 'pending'

    @respx.mock
    def test_unapproved_goes_to_awaiting(self, mock_agent_pool):
        """TSK-AWAIT-001 (pending, is_approved=false) → awaiting_approval."""
        run_step()
        assert task_status('TSK-AWAIT-001') == 'awaiting_approval'

    @respx.mock
    def test_ready_task_dispatched(self, mock_agent_pool):
        """TSK-READY-001 (ready, RES-CODER-003 available) → in_progress."""
        respx.post(url__regex=r".*coder3.*sessions$").respond(201)
        respx.post(url__regex=r".*coder3.*/run$").respond(200, json={"status": "ok"})
        run_step()
        assert task_status('TSK-READY-001') == 'in_progress'
        assert resource_available('RES-CODER-003') is False

    @respx.mock
    def test_busy_resource_blocks_dispatch(self, mock_agent_pool):
        """Tasks on RES-CODER-002 (busy) should not be dispatched."""
        run_step()
        # RES-CODER-002 stays busy
        assert resource_available('RES-CODER-002') is False

    @respx.mock
    def test_pause_mode_blocks_all(self, mock_agent_pool):
        """When paused with 0 steps, no promotion or dispatch occurs."""
        execute_mutation("UPDATE system_state SET value = '\"pause\"' WHERE key = 'run_mode'")
        run_step()
        # TSK-PEND-002 should stay pending (not promoted)
        assert task_status('TSK-PEND-002') == 'pending'

    @respx.mock
    def test_step_mode_executes_once(self, mock_agent_pool):
        """step_count=1 should allow exactly one cycle then stop."""
        execute_mutation("UPDATE system_state SET value = '\"pause\"' WHERE key = 'run_mode'")
        execute_mutation("UPDATE system_state SET value = '1' WHERE key = 'step_count'")
        run_step()
        assert task_status('TSK-PEND-002') == 'ready'  # promoted
        sc = q("SELECT value FROM system_state WHERE key = 'step_count'")
        assert int(sc[0]['value']) == 0


# ═══════════════════════════════════════════════════════════════
#  PHASE 4: RECONCILE
# ═══════════════════════════════════════════════════════════════

class TestReconcile:
    """Verify resource release and event resolution."""

    @respx.mock
    def test_completed_task_releases_resource(self, mock_agent_pool):
        """When TSK-RUN-001 completes, RES-CODER-002 should be released."""
        execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = 'TSK-RUN-001'")
        run_step()
        assert resource_available('RES-CODER-002') is True

    @respx.mock
    def test_resolved_event_lifecycle(self, mock_agent_pool):
        """When a repair task completes, its linked event becomes 'resolved'."""
        # Step 1: Create repair task from event
        run_step()
        assert task_exists('REPAIR-TSK-FAIL-001')

        # Step 2: Simulate PM fixing it
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'REPAIR-TSK-FAIL-001'")
        run_step()

        evts = events_for(task_id='TSK-FAIL-001')
        resolved = [e for e in evts if e['status'] == 'resolved']
        assert len(resolved) >= 1


# ═══════════════════════════════════════════════════════════════
#  MULTI-STEP SCENARIOS
# ═══════════════════════════════════════════════════════════════

class TestMultiStep:
    """End-to-end scenarios across multiple bus cycles."""

    @respx.mock
    def test_full_lifecycle(self, mock_agent_pool):
        """
        3-step lifecycle:
        Step 1: Detect + Promote + Dispatch
        Step 2: Simulate completions → Reconcile
        Step 3: Freed resources pick up next tasks
        """
        respx.post(url__regex=r".*/sessions$").respond(201)
        respx.post(url__regex=r".*/run$").respond(200, json={"status": "ok"})

        # ── Step 1 ──
        run_step()
        assert task_status('TSK-PEND-001') == 'ready'       # dep met, promoted
        assert task_status('TSK-PEND-002') == 'ready'       # no dep, promoted
        assert task_status('TSK-PEND-003') == 'pending'     # dep not met
        assert task_status('TSK-READY-001') == 'in_progress' # dispatched
        assert task_exists('REPAIR-TSK-FAIL-001')           # detected + consumed

        # ── Step 2: Agent finishes work ──
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'TSK-RUN-001'")
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'TSK-READY-001'")
        run_step()
        assert resource_available('RES-CODER-002') is True
        assert resource_available('RES-CODER-003') is True

        # ── Step 3: Freed resources allow new dispatch ──
        run_step()
        # At least one of the promoted tasks should now be dispatched
        statuses = [task_status('TSK-PEND-001'), task_status('TSK-PEND-002')]
        assert 'in_progress' in statuses, f"Expected at least one dispatched, got {statuses}"

    @respx.mock
    def test_chain_promotion(self, mock_agent_pool):
        """
        Verify chained dependencies resolve across cycles:
        TSK-PEND-001 done → TSK-PEND-003 unlocked.
        """
        respx.post(url__regex=r".*/sessions$").respond(201)
        respx.post(url__regex=r".*/run$").respond(200, json={"status": "ok"})

        # Step 1: promote TSK-PEND-001 (dep on done TSK-DONE-001)
        run_step()
        assert task_status('TSK-PEND-001') == 'ready'
        assert task_status('TSK-PEND-003') == 'pending'  # still blocked

        # Step 2: complete TSK-PEND-001
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'TSK-PEND-001'")
        run_step()

        # TSK-PEND-003 should now be promoted (dep met)
        assert task_status('TSK-PEND-003') == 'ready'

    @respx.mock
    def test_event_injection_from_agent(self, mock_agent_pool):
        """
        Simulate an agent calling emit_event() tool → event consumed → repair task created.
        """
        respx.post(url__regex=r".*/sessions$").respond(201)
        respx.post(url__regex=r".*/run$").respond(200, json={"status": "ok"})

        # Agent injects an event (simulating emit_event MCP tool call)
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, task_id, payload)
            VALUES ('task_blocked', 'agent:RES-CODER-002', 'critical', 'ACT-LIVE-001', 'TSK-RUN-001',
                    '{"reason": "Git conflict on main branch, cannot push", "original_status": "blocked"}')
        """)
        execute_mutation("UPDATE tasks SET status = 'blocked', blocker_reason = 'Git conflict' WHERE id = 'TSK-RUN-001'")

        run_step()

        assert task_exists('REPAIR-TSK-RUN-001')
        repair = q("SELECT * FROM tasks WHERE id = 'REPAIR-TSK-RUN-001'")[0]
        assert 'Git conflict' in repair['module_iteration_goal']
