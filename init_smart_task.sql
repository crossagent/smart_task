-- PostgreSQL Initialization Script for Smart Task Hub

-- Note: In PostgreSQL Docker initialization (/docker-entrypoint-initdb.d/), 
-- the database `smart_task_hub` is generally created by the POSTGRES_DB env var.
-- If running manually, ensure you create the DB first and connect to it:
-- CREATE DATABASE smart_task_hub;
-- \c smart_task_hub

-- 1. DROP EXISTING TABLES (Reverse FK order)
DROP TABLE IF EXISTS activity_collaborators CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;
DROP TABLE IF EXISTS modules CASCADE;
DROP TABLE IF EXISTS activities CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS resources CASCADE;

-- 2. Trigger Function to Handle `updated_at` automatically
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 3. Resource Table - '执行人' (Bandwidth/Personnel)
CREATE TABLE IF NOT EXISTS resources (
    id VARCHAR(50) PRIMARY KEY, -- RES-YYYYMMDD-XXXX
    name VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) DEFAULT 'human', -- human | architect | coder
    agent_dir VARCHAR(255) DEFAULT NULL,
    workspace_path VARCHAR(255) DEFAULT NULL,
    is_available BOOLEAN DEFAULT true,
    dingtalk_id VARCHAR(100) DEFAULT NULL,
    professional_skill VARCHAR(255) DEFAULT NULL, -- 程序 | 策划 | 运营 | 美术
    org_role VARCHAR(255) NOT NULL, -- 引擎组组长, 制作人, etc.
    weekly_capacity INT DEFAULT 40,
    status VARCHAR(50) DEFAULT 'Available',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE resources IS 'Bandwidth / Personnel / 执行人 / Agent Slot';
COMMENT ON COLUMN resources.id IS 'RES-YYYYMMDD-XXXX';
COMMENT ON COLUMN resources.status IS 'Available | Busy | Away | Archived';

-- 4. Project Table - '战略项目池' (Inbox / Project Root)
CREATE SCHEMA IF NOT EXISTS adk;
GRANT ALL ON SCHEMA adk TO smart_user;

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(50) PRIMARY KEY, -- PRJ-YYYYMMDD-XXXX
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'Planning',
    initiator_res_id VARCHAR(50) NOT NULL REFERENCES resources(id),
    receiver_res_id VARCHAR(50) DEFAULT NULL REFERENCES resources(id),
    deadline DATE DEFAULT NULL,
    memo_content TEXT NOT NULL,
    ai_summary TEXT DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE projects IS 'Inbox / Project Root / 战略项目池';
COMMENT ON COLUMN projects.id IS 'PRJ-YYYYMMDD-XXXX';
COMMENT ON COLUMN projects.status IS 'Planning | Active | Done | Archived';

-- 5. Activity Table - '执行活动/项目' (Execution Path/Strategy)
CREATE TABLE IF NOT EXISTS activities (
    id VARCHAR(50) PRIMARY KEY, -- ACT-YYYYMMDD-XXXX
    name VARCHAR(255) NOT NULL,
    project_id VARCHAR(50) DEFAULT NULL REFERENCES projects(id),
    owner_res_id VARCHAR(50) NOT NULL REFERENCES resources(id),
    deadline DATE DEFAULT NULL,
    benefit TEXT,
    priority VARCHAR(10) DEFAULT 'P1',
    artifact_url TEXT DEFAULT NULL,
    status VARCHAR(50) DEFAULT 'Active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE activities IS 'Execution Path / Strategy / 执行活动';
COMMENT ON COLUMN activities.id IS 'ACT-YYYYMMDD-XXXX';
COMMENT ON COLUMN activities.priority IS 'P0 | P1 | P2';
COMMENT ON COLUMN activities.status IS 'Active | Done | Archived';

-- 6. Module Table - '物理实体' (Physical Asset/Knowledge Domain / Component Tree)
CREATE TABLE IF NOT EXISTS modules (
    id VARCHAR(50) PRIMARY KEY, -- MOD-YYYYMMDD-XXXX
    name VARCHAR(255) NOT NULL,
    parent_module_id VARCHAR(50) DEFAULT NULL REFERENCES modules(id) ON DELETE SET NULL,
    owner_res_id VARCHAR(50) NOT NULL REFERENCES resources(id),
    knowledge_base TEXT DEFAULT NULL,
    layer_type VARCHAR(100) DEFAULT NULL, -- L1-Domain | L2-Service | L3-Component
    entity_type VARCHAR(100) DEFAULT 'Code', -- Code | Document | Asset | Other
    status VARCHAR(50) DEFAULT 'Active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE modules IS 'Physical Asset / Component Tree / 物理实体';
COMMENT ON COLUMN modules.id IS 'MOD-YYYYMMDD-XXXX';
COMMENT ON COLUMN modules.parent_module_id IS 'Ref to parent Module UUID to form a spatial tree component';
COMMENT ON COLUMN modules.layer_type IS 'Hierarchy scale: L1-Domain | L2-Service | L3-Component';
COMMENT ON COLUMN modules.entity_type IS 'Nature of entity: Code | Document | Asset | Other';
COMMENT ON COLUMN modules.status IS 'Active | Deprecated';

-- 7. Task Table - '最小执行粒子' (Atomic Participant)
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(50) PRIMARY KEY, -- TSK-YYYYMMDD-XXXX
    project_id VARCHAR(50) DEFAULT NULL REFERENCES projects(id),
    activity_id VARCHAR(50) DEFAULT NULL REFERENCES activities(id),
    module_id VARCHAR(50) NOT NULL REFERENCES modules(id),
    resource_id VARCHAR(50) NOT NULL REFERENCES resources(id),
    module_iteration_goal TEXT NOT NULL,
    estimated_hours DECIMAL(10,2) DEFAULT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    depends_on VARCHAR(50)[] DEFAULT '{}',
    start_date DATE DEFAULT NULL,
    due_date DATE DEFAULT NULL,
    artifact_url TEXT DEFAULT NULL,
    redmine_id VARCHAR(50) DEFAULT NULL,
    blocker_reason TEXT DEFAULT NULL,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE tasks IS 'Atomic Participant / 最小执行粒子';
COMMENT ON COLUMN tasks.id IS 'TSK-YYYYMMDD-XXXX';
COMMENT ON COLUMN tasks.module_iteration_goal IS 'Atomic work target (The "Soul" of the task)';
COMMENT ON COLUMN tasks.estimated_hours IS 'Effort estimation (Execution level input - Hours)';
COMMENT ON COLUMN tasks.status IS 'pending | ready | in_progress | code_done | done | failed | blocked | needs_human_help';
COMMENT ON COLUMN tasks.depends_on IS 'Array of preceding Task IDs (Native DAG Topological structure)';
COMMENT ON COLUMN tasks.start_date IS 'Planned start date (Scheduling level input)';
COMMENT ON COLUMN tasks.due_date IS 'Target deadline (Scheduling level input)';
COMMENT ON COLUMN tasks.artifact_url IS 'URL to the deliverable artifact (Doc/Asset/Repo)';
COMMENT ON COLUMN tasks.blocker_reason IS 'Reason why the task failed or is blocked';
COMMENT ON COLUMN tasks.retry_count IS 'Number of times the task was auto-retried';

-- 7.5 Dynamic Progress Views (SQL Inference instead of static columns)
CREATE OR REPLACE VIEW v_module_progress AS
SELECT 
    module_id,
    COUNT(id) as total_tasks,
    COUNT(CASE WHEN status IN ('done', 'code_done') THEN 1 END) as completed_tasks,
    ROUND(
        CASE WHEN COUNT(id) = 0 THEN 0 
        ELSE (COUNT(CASE WHEN status IN ('done', 'code_done') THEN 1 END)::NUMERIC / COUNT(id) * 100) 
        END, 2
    ) as completion_percentage
FROM tasks
GROUP BY module_id;

CREATE OR REPLACE VIEW v_activity_progress AS
SELECT 
    activity_id,
    COUNT(id) as total_tasks,
    COUNT(CASE WHEN status IN ('done', 'code_done') THEN 1 END) as completed_tasks,
    ROUND(
        CASE WHEN COUNT(id) = 0 THEN 0 
        ELSE (COUNT(CASE WHEN status IN ('done', 'code_done') THEN 1 END)::NUMERIC / COUNT(id) * 100) 
        END, 2
    ) as completion_percentage
FROM tasks
WHERE activity_id IS NOT NULL
GROUP BY activity_id;

-- 8. Activity Collaborators Table - '访问控制' (Access Control)
CREATE TABLE IF NOT EXISTS activity_collaborators (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    activity_id VARCHAR(50) NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
    resource_id VARCHAR(50) NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(activity_id, resource_id)
);
COMMENT ON TABLE activity_collaborators IS 'Activity Access Control (who can manage Tasks under this Activity)';

-- 9. Apply Triggers for `updated_at` functionality
DROP TRIGGER IF EXISTS update_resources_modtime ON resources;
CREATE TRIGGER update_resources_modtime BEFORE UPDATE ON resources FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_projects_modtime ON projects;
CREATE TRIGGER update_projects_modtime BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_activities_modtime ON activities;
CREATE TRIGGER update_activities_modtime BEFORE UPDATE ON activities FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_modules_modtime ON modules;
CREATE TRIGGER update_modules_modtime BEFORE UPDATE ON modules FOR EACH ROW EXECUTE FUNCTION update_modified_column();

DROP TRIGGER IF EXISTS update_tasks_modtime ON tasks;
CREATE TRIGGER update_tasks_modtime BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_modified_column();
