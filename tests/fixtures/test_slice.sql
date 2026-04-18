-- ═══════════════════════════════════════════════════════════════
--  TEST SLICE: Repeatable Event Bus Cycle Seed Data
--  
--  Usage:  psql -d smart_task_hub -f test_slice.sql
--          OR inside pytest via execute_mutation(open('...').read())
--
--  This file is IDEMPOTENT. Run it any number of times to reset
--  the database to the exact same known state.
--
--  Design: Covers all major bus cycle scenarios:
--    - Task promotion (pending → ready)
--    - Dependency resolution
--    - Dispatch to agent
--    - Failure detection → event → repair task
--    - Human instruction → event → command task
--    - Stalled activity detection
--    - Resource locking / release
--    - Pause/Step gating
-- ═══════════════════════════════════════════════════════════════

-- 0. CLEAN SLATE (reverse FK order)
DELETE FROM events;
DELETE FROM system_state;
DELETE FROM activity_collaborators;
DELETE FROM tasks;
DELETE FROM modules;
DELETE FROM activities;
DELETE FROM projects;
DELETE FROM resources;

-- ═══════════════════════════════════════════════════════════════
--  1. RESOURCES (Agent Slots)
-- ═══════════════════════════════════════════════════════════════
--  PM slot:      RES-PM-001       — Control Plane / Activity Manager
--  Coder slots:  RES-CODER-001    — Available (will receive dispatched tasks)
--                RES-CODER-002    — Busy (has in_progress task)
--                RES-CODER-003    — Available (idle, no tasks)

INSERT INTO resources (id, name, org_role, workspace_path, is_available, resource_type) VALUES
('RES-PM-001',    'Project Manager',  'Control Plane',  '/app',       TRUE,  'activity_manager'),
('RES-CODER-001', 'Coder Alpha',      'Coder',          '/work/c1',   TRUE,  'agent'),
('RES-CODER-002', 'Coder Beta',       'Coder',          '/work/c2',   FALSE, 'agent'),
('RES-CODER-003', 'Coder Gamma',      'Coder',          '/work/c3',   TRUE,  'agent');


-- ═══════════════════════════════════════════════════════════════
--  2. PROJECT
-- ═══════════════════════════════════════════════════════════════

INSERT INTO projects (id, name, initiator_res_id, memo_content, status) VALUES
('PRJ-TEST-001', 'Test Project: Trading Platform', 'RES-PM-001', 
 'Build a modular trading platform with auth, API, and data pipeline.', 'Active');


-- ═══════════════════════════════════════════════════════════════
--  3. ACTIVITIES
-- ═══════════════════════════════════════════════════════════════
--  ACT-LIVE-001  — Active sprint with mixed task states (main test target)
--  ACT-STALL-001 — All tasks terminal → should trigger activity_stalled event

INSERT INTO activities (id, name, project_id, owner_res_id, status, priority, user_instruction, instruction_version) VALUES
('ACT-LIVE-001',  'Sprint: Core Auth & API',     'PRJ-TEST-001', 'RES-PM-001', 'Active', 'P0', NULL, 0),
('ACT-STALL-001', 'Sprint: Legacy Data Migration','PRJ-TEST-001', 'RES-PM-001', 'Active', 'P1', NULL, 0);


-- ═══════════════════════════════════════════════════════════════
--  4. MODULES (Component Tree)
-- ═══════════════════════════════════════════════════════════════

INSERT INTO modules (id, name, owner_res_id, layer_type, entity_type) VALUES
('MOD-AUTH-001',     'Authentication Service', 'RES-CODER-001', 'L2-Service',   'Code'),
('MOD-API-001',      'REST API Gateway',       'RES-CODER-001', 'L2-Service',   'Code'),
('MOD-DATA-001',     'Data Pipeline',          'RES-CODER-002', 'L2-Service',   'Code'),
('MOD-LEGACY-001',   'Legacy Migrator',        'RES-CODER-003', 'L2-Service',   'Code');


-- ═══════════════════════════════════════════════════════════════
--  5. TASKS — The Core Test Slice
-- ═══════════════════════════════════════════════════════════════
--
--  ACT-LIVE-001 DAG (main test focus):
--  
--    TSK-DONE-001 (done)
--         ↓
--    TSK-PEND-001 (pending, dep met)     TSK-PEND-002 (pending, no dep)
--         ↓
--    TSK-PEND-003 (pending, dep NOT met — waits for TSK-PEND-001)
--
--    TSK-READY-001 (ready, resource available → will be dispatched)
--    TSK-RUN-001   (in_progress, resource busy → occupies RES-CODER-002)
--    TSK-FAIL-001  (failed → should trigger task_failed event)
--    TSK-BLOCK-001 (blocked → should trigger task_blocked event)
--    TSK-AWAIT-001 (pending, is_approved=false → should go to awaiting_approval)
--
--  ACT-STALL-001 (stalled — all terminal):
--    TSK-STALL-D1 (done)
--    TSK-STALL-D2 (done)
--    TSK-STALL-F1 (failed)
--

-- ── ACT-LIVE-001: Mixed states ──

INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id,
                   module_iteration_goal, estimated_hours, status, depends_on, 
                   is_approved, blocker_reason, execution_result) VALUES

-- Completed anchor
('TSK-DONE-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-AUTH-001', 'RES-CODER-001',
 'Setup PostgreSQL schema and migration scripts', 2.0, 'done', '{}',
 TRUE, NULL, 'Schema created. 5 tables, 3 views. Migration v1 applied.'),

-- Pending: dependency met (depends on TSK-DONE-001 which is done)
('TSK-PEND-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-AUTH-001', 'RES-CODER-001',
 'Implement JWT authentication middleware', 3.0, 'pending', '{TSK-DONE-001}',
 TRUE, NULL, NULL),

-- Pending: no dependency
('TSK-PEND-002', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-API-001', 'RES-CODER-001',
 'Create OpenAPI spec for REST endpoints', 1.5, 'pending', '{}',
 TRUE, NULL, NULL),

-- Pending: dependency NOT met (depends on TSK-PEND-001 which is still pending)
('TSK-PEND-003', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-AUTH-001', 'RES-CODER-001',
 'Add role-based access control layer', 4.0, 'pending', '{TSK-PEND-001}',
 TRUE, NULL, NULL),

-- Ready: will be dispatched to RES-CODER-003 (available)
('TSK-READY-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-API-001', 'RES-CODER-003',
 'Build health check and monitoring endpoints', 1.0, 'ready', '{}',
 TRUE, NULL, NULL),

-- In Progress: occupies RES-CODER-002 (busy)
('TSK-RUN-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-DATA-001', 'RES-CODER-002',
 'Implement real-time market data ingestion pipeline', 5.0, 'in_progress', '{}',
 TRUE, NULL, NULL),

-- Failed: should trigger task_failed event → repair task
('TSK-FAIL-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-DATA-001', 'RES-CODER-002',
 'Integrate Binance WebSocket feed', 2.0, 'failed', '{}',
 TRUE, 'WebSocket connection rejected: API rate limit exceeded. Need IP whitelist.', NULL),

-- Blocked: should trigger task_blocked event → repair task  
('TSK-BLOCK-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-API-001', 'RES-CODER-001',
 'Implement order execution REST endpoint', 3.0, 'blocked', '{TSK-DONE-001}',
 TRUE, 'Waiting for exchange sandbox credentials from DevOps team.', NULL),

-- Pending but NOT approved: should go to awaiting_approval (not ready)
('TSK-AWAIT-001', 'PRJ-TEST-001', 'ACT-LIVE-001', 'MOD-AUTH-001', 'RES-CODER-001',
 'Deploy auth service to production', 1.0, 'pending', '{}',
 FALSE, NULL, NULL);


-- ── ACT-STALL-001: All terminal (stalled activity) ──

INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id,
                   module_iteration_goal, estimated_hours, status, depends_on,
                   is_approved, blocker_reason, execution_result) VALUES

('TSK-STALL-D1', 'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-LEGACY-001', 'RES-CODER-003',
 'Export legacy MySQL data to CSV', 2.0, 'done', '{}',
 TRUE, NULL, 'Exported 12 tables, 2.3M rows.'),

('TSK-STALL-D2', 'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-LEGACY-001', 'RES-CODER-003',
 'Transform CSV to new schema format', 3.0, 'done', '{TSK-STALL-D1}',
 TRUE, NULL, 'Transformation complete. 98.7% data integrity.'),

('TSK-STALL-F1', 'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-LEGACY-001', 'RES-CODER-003',
 'Load transformed data into PostgreSQL', 2.0, 'failed', '{TSK-STALL-D2}',
 TRUE, 'COPY command failed: encoding mismatch on 3 columns (legacy GB2312 data).', NULL);


-- ═══════════════════════════════════════════════════════════════
--  6. SYSTEM STATE
-- ═══════════════════════════════════════════════════════════════

INSERT INTO system_state (key, value) VALUES ('run_mode', '"auto"');
INSERT INTO system_state (key, value) VALUES ('step_count', '0');


-- ═══════════════════════════════════════════════════════════════
--  7. PRE-SEEDED EVENTS (Optional: uncomment to test consumption)
-- ═══════════════════════════════════════════════════════════════
--  These simulate events that have already been detected but not yet consumed.
--  Uncomment the block below to test Phase 2 (consumption) in isolation.

-- INSERT INTO events (event_type, source, severity, activity_id, task_id, payload) VALUES
-- ('task_failed',   'scheduler', 'warning',  'ACT-LIVE-001', 'TSK-FAIL-001',
--  '{"reason": "WebSocket connection rejected: API rate limit exceeded.", "original_status": "failed", "module_id": "MOD-DATA-001"}'),
-- ('task_blocked',  'scheduler', 'warning',  'ACT-LIVE-001', 'TSK-BLOCK-001',
--  '{"reason": "Waiting for exchange sandbox credentials from DevOps team.", "original_status": "blocked", "module_id": "MOD-API-001"}');


-- ═══════════════════════════════════════════════════════════════
--  VERIFICATION SUMMARY  (run after seeding to confirm)
-- ═══════════════════════════════════════════════════════════════
--
--  Expected counts:
--    Resources:  4  (1 PM + 3 Coders)
--    Projects:   1
--    Activities: 2  (1 Active live, 1 Active stalled)
--    Modules:    4
--    Tasks:     12  (1 done, 3 pending, 1 ready, 1 in_progress, 
--                    1 failed, 1 blocked, 1 pending-unapproved,
--                    2 stall-done, 1 stall-failed)
--    Events:     0  (clean — scheduler will detect on first cycle)
--
--  After 1 bus cycle, expect:
--    New events:     3+ (task_failed for TSK-FAIL-001, 
--                        task_blocked for TSK-BLOCK-001,
--                        activity_stalled for ACT-STALL-001)
--    Promoted:       TSK-PEND-001 → ready (dep met)
--                    TSK-PEND-002 → ready (no dep)
--                    TSK-AWAIT-001 → awaiting_approval (not approved)
--    NOT promoted:   TSK-PEND-003 (dep TSK-PEND-001 still pending at detect time)
--    Dispatched:     TSK-READY-001 → in_progress (if agent pool has RES-CODER-003)
--    Repair tasks:   REPAIR-TSK-FAIL-001, REPAIR-TSK-BLOCK-001
