"""
Event Bus Cycle Integration Test Suite.

Tests the full 4-phase scheduler cycle (Detect → Consume → Execute → Reconcile)
against a REAL database with MOCKED agent dispatch.

Test Slice Template:
    - 1 Project (P1)
    - 1 Activity (A1, Active)
    - 2 Modules (M1, M2)
    - 6 Tasks in various lifecycle states
    - Pre-seeded Events for consumption testing
    - Agent pool mocked (no real LLM calls)

Each test case runs one or more bus cycles (steps) and asserts DB state transitions.
"""

import pytest
import respx
import json
from unittest.mock import MagicMock, patch
from src.task_execution.scheduler import run_system_bus_cycle
from src.resource_management.supervisor import agent_supervisor
from src.task_management.db import execute_query, execute_mutation


# ═══════════════════════════════════════════════════════════════
#  FIXTURES: Test Slice Template
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clean_and_seed_db(db_conn):
    """
    Reset DB to a known state before each test.
    Seeds a 'test slice' with various task/event states.
    """
    # ── CLEAN ──
    execute_mutation("DELETE FROM events")
    execute_mutation("DELETE FROM system_state")
    execute_mutation("DELETE FROM tasks")
    execute_mutation("DELETE FROM modules")
    execute_mutation("DELETE FROM activities")
    execute_mutation("DELETE FROM projects")
    execute_mutation("DELETE FROM resources")
    
    # ── SEED: System State ──
    execute_mutation("INSERT INTO system_state (key, value) VALUES ('run_mode', '\"auto\"')")
    execute_mutation("INSERT INTO system_state (key, value) VALUES ('step_count', '0')")
    
    # ── SEED: Resources (Agent Slots) ──
    execute_mutation("""
        INSERT INTO resources (id, name, org_role, workspace_path, is_available, resource_type) VALUES
        ('RES-ARCHITECT-001', 'System Architect', 'Control Plane', '/app', True, 'activity_manager'),
        ('RES-CODER-001',     'Coder Agent 1',   'Coder',         '/work/c1', True, 'agent'),
        ('RES-CODER-002',     'Coder Agent 2',   'Coder',         '/work/c2', True, 'agent')
    """)
    
    # ── SEED: Project ──
    execute_mutation("""
        INSERT INTO projects (id, name, initiator_res_id, memo_content)
        VALUES ('P1', 'Test Project Alpha', 'RES-ARCHITECT-001', 'Integration testing project')
    """)
    
    # ── SEED: Activity ──
    execute_mutation("""
        INSERT INTO activities (id, name, project_id, owner_res_id, status)
        VALUES ('A1', 'Feature Sprint', 'P1', 'RES-ARCHITECT-001', 'Active')
    """)
    
    # ── SEED: Modules ──
    execute_mutation("""
        INSERT INTO modules (id, name, owner_res_id) VALUES
        ('M1', 'Auth Module', 'RES-CODER-001'),
        ('M2', 'API Module',  'RES-CODER-002')
    """)
    
    # ── SEED: Tasks (The Core Test Slice) ──
    # T1: pending, no deps → should be promoted to ready
    # T2: pending, depends on T3 (done) → should be promoted to ready
    # T3: done → stable, used as dependency
    # T4: ready → should be dispatched to agent
    # T5: failed → should trigger event detection
    # T6: in_progress → stable (resource busy)
    execute_mutation("""
        INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, 
                           module_iteration_goal, status, depends_on, blocker_reason) VALUES
        ('T1', 'P1', 'A1', 'M1', 'RES-CODER-001', 'Implement login endpoint',   'pending',      '{}',     NULL),
        ('T2', 'P1', 'A1', 'M1', 'RES-CODER-001', 'Add JWT validation',         'pending',      '{T3}',   NULL),
        ('T3', 'P1', 'A1', 'M1', 'RES-CODER-001', 'Setup database schema',      'done',         '{}',     NULL),
        ('T4', 'P1', 'A1', 'M2', 'RES-CODER-002', 'Build REST endpoints',       'ready',        '{}',     NULL),
        ('T5', 'P1', 'A1', 'M2', 'RES-CODER-002', 'Integrate payment gateway',  'failed',       '{}',     'API key expired'),
        ('T6', 'P1', 'A1', 'M1', 'RES-CODER-001', 'Write unit tests',           'in_progress',  '{}',     NULL)
    """)
    
    # Mark RES-CODER-001 as busy (T6 is in_progress)
    execute_mutation("UPDATE resources SET is_available = False WHERE id = 'RES-CODER-001'")
    
    yield
    
    # ── CLEANUP ──
    execute_mutation("DELETE FROM events")
    execute_mutation("DELETE FROM system_state")
    execute_mutation("DELETE FROM tasks")
    execute_mutation("DELETE FROM modules")
    execute_mutation("DELETE FROM activities")
    execute_mutation("DELETE FROM projects")
    execute_mutation("DELETE FROM resources")


@pytest.fixture
def mock_agent_pool():
    """Mock the agent supervisor pool — no real LLM calls."""
    original_pool = agent_supervisor.pool
    agent_supervisor.pool = {
        "RES-CODER-001": {"url": "http://coder1:9001", "agent_id": "coder-agent-1"},
        "RES-CODER-002": {"url": "http://coder2:9002", "agent_id": "coder-agent-2"},
        "RES-ARCHITECT-001": {"url": "http://pm:9010", "agent_id": "pm-agent"},
    }
    yield agent_supervisor.pool
    agent_supervisor.pool = original_pool


def run_step():
    """Execute a single bus cycle with threading mocked to run synchronously."""
    with patch("src.task_execution.scheduler.threading.Thread") as mock_thread:
        def sync_run(target, args=(), kwargs={}, daemon=True):
            target(*args, **kwargs)
            return MagicMock()
        mock_thread.side_effect = sync_run
        run_system_bus_cycle()


def get_task_status(task_id: str) -> str:
    """Helper: fetch a single task's status."""
    rows = execute_query("SELECT status FROM tasks WHERE id = %s", (task_id,))
    return rows[0]['status'] if rows else None


def get_resource_available(res_id: str) -> bool:
    """Helper: check if a resource is available."""
    rows = execute_query("SELECT is_available FROM resources WHERE id = %s", (res_id,))
    return rows[0]['is_available'] if rows else None


def get_pending_events(event_type: str = None) -> list:
    """Helper: fetch pending events, optionally filtered by type."""
    if event_type:
        return execute_query(
            "SELECT * FROM events WHERE status = 'pending' AND event_type = %s",
            (event_type,)
        )
    return execute_query("SELECT * FROM events WHERE status = 'pending'")


def get_all_events() -> list:
    """Helper: fetch all events."""
    return execute_query("SELECT * FROM events ORDER BY created_at ASC")


# ═══════════════════════════════════════════════════════════════
#  TEST CASES
# ═══════════════════════════════════════════════════════════════

class TestPhase1_EventDetection:
    """Tests that the Detect phase correctly emits events from system anomalies."""

    @respx.mock
    def test_failed_task_emits_event(self, mock_agent_pool):
        """A failed task (T5) should produce a task_failed event."""
        # The test slice has T5 in 'failed' state
        run_step()
        
        events = get_pending_events('task_failed')
        # Event might be already consumed in same cycle, check all events
        all_evts = execute_query(
            "SELECT * FROM events WHERE event_type = 'task_failed' AND task_id = 'T5'"
        )
        assert len(all_evts) >= 1, "Expected a task_failed event for T5"
        
        evt = all_evts[0]
        payload = json.loads(evt['payload']) if isinstance(evt['payload'], str) else evt['payload']
        assert payload['reason'] == 'API key expired'
        assert evt['activity_id'] == 'A1'

    @respx.mock
    def test_no_duplicate_events(self, mock_agent_pool):
        """Running two cycles should NOT create duplicate pending events for the same task."""
        run_step()
        run_step()  # Second cycle
        
        # Count events for T5 — should be exactly 1 (dedup index)
        all_evts = execute_query(
            "SELECT * FROM events WHERE event_type = 'task_failed' AND task_id = 'T5'"
        )
        # There may be multiple if the first was resolved and a new one created,
        # but there should be at most 1 pending
        pending = [e for e in all_evts if e['status'] == 'pending']
        assert len(pending) <= 1, f"Expected at most 1 pending event for T5, got {len(pending)}"

    @respx.mock
    def test_human_instruction_event(self, mock_agent_pool):
        """Updating activity instruction should produce a human_instruction event."""
        # Simulate human updating instructions
        execute_mutation("""
            UPDATE activities 
            SET user_instruction = 'Please prioritize security',
                instruction_version = 1
            WHERE id = 'A1'
        """)
        
        run_step()
        
        all_evts = execute_query(
            "SELECT * FROM events WHERE event_type = 'human_instruction' AND activity_id = 'A1'"
        )
        assert len(all_evts) >= 1, "Expected a human_instruction event for A1"


class TestPhase2_EventConsumption:
    """Tests that events are consumed and translated into Task mutations."""

    @respx.mock
    def test_failed_task_creates_repair_task(self, mock_agent_pool):
        """A task_failed event should create a REPAIR-T5 task for the PM."""
        run_step()  # Detect + Consume in one cycle
        
        repair = execute_query("SELECT * FROM tasks WHERE id = 'REPAIR-T5'")
        assert len(repair) == 1, "Expected a repair task REPAIR-T5"
        assert repair[0]['resource_id'] == 'RES-ARCHITECT-001'
        assert repair[0]['status'] == 'ready'
        assert 'INTERRUPT SIGNAL' in repair[0]['module_iteration_goal']

    @respx.mock
    def test_event_marked_processing_after_consumption(self, mock_agent_pool):
        """After creating a repair task, the event should be marked 'processing'."""
        run_step()
        
        evts = execute_query(
            "SELECT * FROM events WHERE task_id = 'T5' AND event_type = 'task_failed'"
        )
        assert len(evts) >= 1
        # At least one should be processing or resolved
        statuses = [e['status'] for e in evts]
        assert 'processing' in statuses or 'resolved' in statuses, \
            f"Expected event to be processing/resolved, got {statuses}"

    @respx.mock
    def test_human_command_creates_cmd_task(self, mock_agent_pool):
        """A human_instruction event should create a CMD task for the PM."""
        # Pre-inject an event (as if human wrote it)
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, payload)
            VALUES ('human_instruction', 'human', 'critical', 'A1', 
                    '{"instruction": "Focus on security", "version": 1}')
        """)
        
        run_step()
        
        cmd = execute_query("SELECT * FROM tasks WHERE id = 'CMD-A1-V1'")
        assert len(cmd) == 1, "Expected a command task CMD-A1-V1"
        assert cmd[0]['resource_id'] == 'RES-ARCHITECT-001'
        assert 'HUMAN COMMAND' in cmd[0]['module_iteration_goal']


class TestPhase3_DataPlane:
    """Tests task promotion and dispatch."""

    @respx.mock
    def test_pending_task_promoted_to_ready(self, mock_agent_pool):
        """T1 (pending, no deps) should be promoted to ready."""
        run_step()
        assert get_task_status('T1') == 'ready'

    @respx.mock
    def test_pending_task_with_met_deps_promoted(self, mock_agent_pool):
        """T2 (pending, depends on T3 which is done) should be promoted."""
        run_step()
        assert get_task_status('T2') == 'ready'

    @respx.mock
    def test_ready_task_dispatched(self, mock_agent_pool):
        """T4 (ready, resource available) should be dispatched to the agent."""
        # Mock agent HTTP endpoints
        respx.post("http://coder2:9002/apps/coder-agent-2/users/smart-task-scheduler/sessions").respond(201)
        respx.post("http://coder2:9002/run").respond(200, json={"status": "ok"})
        
        run_step()
        
        assert get_task_status('T4') == 'in_progress'
        assert get_resource_available('RES-CODER-002') is False

    @respx.mock
    def test_paused_mode_blocks_execution(self, mock_agent_pool):
        """When run_mode=pause and step_count=0, no promotion/dispatch should occur."""
        execute_mutation("UPDATE system_state SET value = '\"pause\"' WHERE key = 'run_mode'")
        
        run_step()
        
        # T1 should remain pending (not promoted)
        assert get_task_status('T1') == 'pending'

    @respx.mock
    def test_step_mode_executes_once(self, mock_agent_pool):
        """step_count=1 should allow exactly one cycle of promotion/dispatch."""
        execute_mutation("UPDATE system_state SET value = '\"pause\"' WHERE key = 'run_mode'")
        execute_mutation("UPDATE system_state SET value = '1' WHERE key = 'step_count'")
        
        run_step()
        
        # T1 should be promoted
        assert get_task_status('T1') == 'ready'
        
        # Step count should be decremented to 0
        sc = execute_query("SELECT value FROM system_state WHERE key = 'step_count'")
        assert int(sc[0]['value']) == 0

    @respx.mock
    def test_busy_resource_blocks_dispatch(self, mock_agent_pool):
        """T1/T2 use RES-CODER-001 which is busy (T6 in_progress). Should not dispatch."""
        respx.post("http://coder2:9002/apps/coder-agent-2/users/smart-task-scheduler/sessions").respond(201)
        respx.post("http://coder2:9002/run").respond(200, json={"status": "ok"})
        
        run_step()
        
        # T1 was promoted to ready, but resource is busy → stays ready, not in_progress
        assert get_task_status('T1') == 'ready'
        # RES-CODER-001 remains busy
        assert get_resource_available('RES-CODER-001') is False


class TestPhase4_Reconcile:
    """Tests resource release and event resolution on task completion."""

    @respx.mock
    def test_completed_task_releases_resource(self, mock_agent_pool):
        """When T6 completes, RES-CODER-001 should be released."""
        # Simulate agent completion
        execute_mutation("UPDATE tasks SET status = 'code_done' WHERE id = 'T6'")
        
        run_step()
        
        assert get_resource_available('RES-CODER-001') is True

    @respx.mock
    def test_reconcile_resolves_linked_events(self, mock_agent_pool):
        """When a repair task completes, its linked event should be resolved."""
        # Step 1: Let the cycle detect T5 failure and create REPAIR-T5
        run_step()
        
        # Verify repair task exists
        repair = execute_query("SELECT * FROM tasks WHERE id = 'REPAIR-T5'")
        assert len(repair) == 1
        
        # Step 2: Simulate PM completing the repair task
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'REPAIR-T5'")
        
        run_step()  # Reconcile
        
        # The event that spawned REPAIR-T5 should now be 'resolved'
        evts = execute_query(
            "SELECT * FROM events WHERE resolved_by = 'REPAIR-T5'"
        )
        assert len(evts) >= 1
        assert evts[0]['status'] == 'resolved'


class TestMultiStepScenario:
    """End-to-end multi-step scenario testing the full lifecycle."""

    @respx.mock
    def test_full_lifecycle_3_steps(self, mock_agent_pool):
        """
        Step 1: Detect anomalies + promote pending tasks + dispatch ready tasks
        Step 2: Simulate agent completing work → reconcile
        Step 3: Verify clean state
        """
        # Mock all agent endpoints
        respx.post(url__regex=r".*/sessions$").respond(201)
        respx.post(url__regex=r".*/run$").respond(200, json={"status": "ok"})
        
        # ── STEP 1 ──
        run_step()
        
        # T1: pending → ready (promoted, but resource busy)
        assert get_task_status('T1') == 'ready'
        # T2: pending → ready (dep T3 is done, but resource busy) 
        assert get_task_status('T2') == 'ready'
        # T4: ready → in_progress (dispatched)
        assert get_task_status('T4') == 'in_progress'
        # T5 failure detected → REPAIR task created
        repair = execute_query("SELECT id FROM tasks WHERE id = 'REPAIR-T5'")
        assert len(repair) == 1
        
        # ── STEP 2: Simulate agent results ──
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'T4'")
        execute_mutation("UPDATE tasks SET status = 'done' WHERE id = 'T6'")
        
        run_step()
        
        # Resources released
        assert get_resource_available('RES-CODER-001') is True
        assert get_resource_available('RES-CODER-002') is True
        
        # ── STEP 3: Now T1/T2 can be dispatched ──
        run_step()
        
        # With resource free, T1 or T2 should now be dispatched
        t1_status = get_task_status('T1')
        t2_status = get_task_status('T2')
        # At least one should be in_progress (both on same resource, one dispatched)
        assert t1_status == 'in_progress' or t2_status == 'in_progress', \
            f"Expected dispatch after resource freed: T1={t1_status}, T2={t2_status}"

    @respx.mock
    def test_event_injection_triggers_pm(self, mock_agent_pool):
        """
        Inject a custom event → verify it creates a task on next cycle.
        This simulates an agent or human writing an event via emit_event() tool.
        """
        respx.post(url__regex=r".*/sessions$").respond(201)
        respx.post(url__regex=r".*/run$").respond(200, json={"status": "ok"})
        
        # Inject a custom event
        execute_mutation("""
            INSERT INTO events (event_type, source, severity, activity_id, task_id, payload)
            VALUES ('task_blocked', 'agent:RES-CODER-001', 'warning', 'A1', 'T6',
                    '{"reason": "Git merge conflict on main branch", "original_status": "blocked"}')
        """)
        # Also update T6 status to match
        execute_mutation("UPDATE tasks SET status = 'blocked', blocker_reason = 'Git merge conflict' WHERE id = 'T6'")
        
        run_step()
        
        # Should create REPAIR-T6
        repair = execute_query("SELECT * FROM tasks WHERE id = 'REPAIR-T6'")
        assert len(repair) == 1, "Expected REPAIR-T6 task from injected event"
        assert repair[0]['resource_id'] == 'RES-ARCHITECT-001'
