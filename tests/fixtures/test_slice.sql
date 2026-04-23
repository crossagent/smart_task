-- ==============================================================================
--  TEST SLICE SEED DATA
--  A designed, repeatable test slice covering:
--    - Chained task dependencies
--    - Multiple activities (Healthy vs Stalled)
--    - Resource locking / release
--    - Pause/Step gating
-- ==============================================================================

-- 0. CLEAN SLATE (reverse FK order)
DELETE FROM events;
DELETE FROM system_state;
DELETE FROM activity_collaborators;
DELETE FROM tasks;
DELETE FROM modules;
DELETE FROM activities;
DELETE FROM projects;
DELETE FROM resources;

-- ==============================================================================
--  1. RESOURCES (Agent Slots)
-- ==============================================================================
--  PM slot:      RES-ARCHITECT-001 - Control Plane / Activity Manager
INSERT INTO resources (id, name, org_role, resource_type, is_available) 
VALUES ('RES-ARCHITECT-001', 'Senior Architect PM', 'pm', 'agent', TRUE);

--  Coder slots:
INSERT INTO resources (id, name, org_role, resource_type, is_available) 
VALUES ('RES-CODER-001', 'Coder Alpha', 'developer', 'agent', TRUE);

INSERT INTO resources (id, name, org_role, resource_type, is_available) 
VALUES ('RES-CODER-002', 'Coder Beta', 'developer', 'agent', FALSE); -- Busy with TSK-RUN-001

INSERT INTO resources (id, name, org_role, resource_type, is_available) 
VALUES ('RES-CODER-003', 'Coder Gamma', 'developer', 'agent', TRUE);


-- ==============================================================================
--  2. SYSTEM STATE
-- ==============================================================================
INSERT INTO system_state (key, value) VALUES ('run_mode', '"auto"');
INSERT INTO system_state (key, value) VALUES ('step_count', '0');


-- ==============================================================================
--  3. PROJECTS & ACTIVITIES
-- ==============================================================================

-- Project A: Active development
INSERT INTO projects (id, name, owner_res_id, status) 
VALUES ('PRJ-ACTIVE-001', 'Auth Service Refactor', 'RES-ARCHITECT-001', 'in_progress');

INSERT INTO activities (id, project_id, name, owner_res_id, status) 
VALUES ('ACT-LIVE-001', 'PRJ-ACTIVE-001', 'Implement OAuth2', 'RES-ARCHITECT-001', 'in_progress');

-- Project B: Stalled (to test anomaly detection)
INSERT INTO projects (id, name, owner_res_id, status) 
VALUES ('PRJ-STALL-001', 'Legacy Migration', 'RES-ARCHITECT-001', 'stalled');

INSERT INTO activities (id, project_id, name, owner_res_id, status) 
VALUES ('ACT-STALL-001', 'PRJ-STALL-001', 'Database Schema Mapping', 'RES-ARCHITECT-001', 'stalled');


-- ==============================================================================
--  4. MODULES
-- ==============================================================================
INSERT INTO modules (id, project_id, name, owner_res_id) 
VALUES ('MOD-AUTH-CORE', 'PRJ-ACTIVE-001', 'Auth Core', 'RES-ARCHITECT-001');

INSERT INTO modules (id, project_id, name, owner_res_id) 
VALUES ('MOD-LEGACY-DB', 'PRJ-STALL-001', 'Legacy DB Parser', 'RES-ARCHITECT-001');


-- ==============================================================================
--  5. TASKS (The core of the test slice)
-- ==============================================================================

-- SCENARIO: Chain of dependencies
-- TSK-DONE-001 (DONE) -> TSK-PEND-001 (PENDING) -> TSK-PEND-003 (PENDING)
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-DONE-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'done', 'Setup repo', TRUE);

INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, depends_on, is_approved)
VALUES ('TSK-PEND-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'pending', 'Implement JWT logic', 'TSK-DONE-001', TRUE);

INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, depends_on, is_approved)
VALUES ('TSK-PEND-003', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'pending', 'Write unit tests', 'TSK-PEND-001', TRUE);

-- SCENARIO: Task with no dependencies, should be promoted to READY immediately
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-PEND-002', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'pending', 'Doc review', TRUE);

-- SCENARIO: Task that is PENDING but NOT APPROVED
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-AWAIT-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'pending', 'Dangerous database migration', FALSE);

-- SCENARIO: A task already running on a resource
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-RUN-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-002', 'in_progress', 'Debugging session manager', TRUE);

-- SCENARIO: A task READY to be dispatched
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-READY-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-003', 'ready', 'Refactor logger', TRUE);


-- ANOMALY SCENARIO: A FAILED task that needs REPAIR
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, blocker_reason, is_approved)
VALUES ('TSK-FAIL-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'failed', 'API Integration', 'Rate limit exceeded', TRUE);

-- ANOMALY SCENARIO: A BLOCKED task
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, blocker_reason, is_approved)
VALUES ('TSK-BLOCK-001', 'PRJ-ACTIVE-001', 'ACT-LIVE-001', 'MOD-AUTH-CORE', 'RES-CODER-001', 'blocked', 'Secrets setup', 'Missing vault keys', TRUE);

-- ANOMALY SCENARIO: Activity ACT-STALL-001 is stalled because all its tasks are terminal
INSERT INTO tasks (id, project_id, activity_id, module_id, resource_id, status, module_iteration_goal, is_approved)
VALUES ('TSK-DONE-002', 'PRJ-STALL-001', 'ACT-STALL-001', 'MOD-LEGACY-DB', 'RES-CODER-001', 'done', 'Scan legacy tables', TRUE);
