-- ==============================================================================
--  TEST SLICE - REFINED (Module-Centric Schema)
--  Idempotent seed data for Integration Tests
-- ==============================================================================

-- 1. CLEANUP
TRUNCATE task_assignments, events, tasks, modules, activities, projects, resources, system_state CASCADE;

-- 2. RESOURCES
INSERT INTO resources (id, name, org_role, is_available, resource_type) VALUES
('RES-ARCHITECT-001', 'System Architect', 'Control Plane', TRUE,  'agent'),
('RES-CODER-001',     'Coder One',        'Coder',         TRUE,  'human'),
('RES-CODER-002',     'Bob Coder',        'Coder',         TRUE,  'human'),
('RES-CODER-003',     'Coder Three',      'Coder',         TRUE,  'human'),
('RES-CODER-004',     'Dave Coder',       'Coder',         TRUE,  'human');

-- 3. MODULES (Physical Entities)
INSERT INTO modules (id, name, owner_res_id, local_path, repo_url, entity_type) VALUES
('MOD-ROOT',      'System Root',   'RES-ARCHITECT-001', '/app',           'git://hub.local/root',    'Code'),
('MOD-AUTH',      'Auth Service',  'RES-CODER-001',     '/app/src/auth',  'git://hub.local/auth',    'Code'),
('MOD-DB',        'DB Layer',      'RES-CODER-002',     '/app/src/db',    'git://hub.local/db',      'Code'),
('MOD-UI',        'Frontend UI',   'RES-CODER-003',     '/app/src/ui',    'git://hub.local/ui',      'Code'),
('MOD-DOCS',      'System Docs',   'RES-ARCHITECT-001', '/app/docs',      'git://hub.local/docs',    'Document');

-- 4. PROJECTS
INSERT INTO projects (id, name, initiator_res_id, memo_content, status) VALUES
('PRJ-LIVE-001',  'Production Migration', 'RES-ARCHITECT-001', 'Migrate all services to PG17', 'Active'),
('PRJ-TEST-001',  'Integration Testing',  'RES-ARCHITECT-001', 'Test the event bus cycle',    'Active');

-- 5. ACTIVITIES
INSERT INTO activities (id, project_id, name, owner_res_id, status) VALUES
('ACT-LIVE-001',  'PRJ-LIVE-001', 'Phase 1: Auth Migration', 'RES-ARCHITECT-001', 'Active'),
('ACT-STALL-001', 'PRJ-TEST-001', 'Stalled Activity',        'RES-ARCHITECT-001', 'Active');

-- 6. TASKS
INSERT INTO tasks (id, project_id, activity_id, module_id, module_iteration_goal, status, is_approved) VALUES
-- Terminal States
('TSK-DONE-001',  'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-DB',   'Setup DB Schema',   'done',      TRUE),
('TSK-FAIL-001',  'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-AUTH', 'Init Auth Config',  'failed',    TRUE),
('TSK-BLOCK-001', 'PRJ-TEST-001', 'ACT-STALL-001', 'MOD-UI',   'Design Login UI',   'blocked',   TRUE),

-- Pending / Ready States
('TSK-PEND-001',  'PRJ-LIVE-001', 'ACT-LIVE-001',  'MOD-AUTH', 'Implement OAuth2',  'pending',   TRUE),
('TSK-PEND-002',  'PRJ-LIVE-001', 'ACT-LIVE-001',  'MOD-DOCS', 'Write API Docs',    'pending',   TRUE),
('TSK-AWAIT-001', 'PRJ-LIVE-001', 'ACT-LIVE-001',  'MOD-UI',   'Build Dashboard',   'pending',   FALSE),
('TSK-READY-001', 'PRJ-LIVE-001', 'ACT-LIVE-001',  'MOD-UI',   'Fix CSS Bugs',      'ready',     TRUE),

-- In-Progress (Running)
('TSK-RUN-001',   'PRJ-LIVE-001', 'ACT-LIVE-001',  'MOD-DB',   'Optimize Queries',  'in_progress', TRUE);

-- Set dependencies
UPDATE tasks SET depends_on = '{TSK-DONE-001}' WHERE id = 'TSK-PEND-001';
UPDATE tasks SET depends_on = '{TSK-PEND-001}' WHERE id = 'TSK-PEND-003'; -- TSK-PEND-003 not in seed, skip

-- 7. ASSIGNMENTS
INSERT INTO task_assignments (task_id, resource_id, status) VALUES
('TSK-RUN-001', 'RES-CODER-002', 'active');

-- 8. SYSTEM STATE
INSERT INTO system_state (key, value) VALUES 
('run_mode', '"auto"'),
('step_count', '0');
