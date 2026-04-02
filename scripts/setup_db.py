import sqlite3
import os

DB_PATH = "smart_task.db"

def main():
    if os.path.exists(DB_PATH):
        print(f"Removing existing {DB_PATH} for a fresh start.")
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tables
    cursor.execute('''CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT DEFAULT 'Planning',
        initiator_res_id TEXT NOT NULL,
        receiver_res_id TEXT,
        deadline TEXT,
        memo_content TEXT NOT NULL,
        ai_summary TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS activities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        project_id TEXT,
        owner_res_id TEXT NOT NULL,
        deadline TEXT,
        benefit TEXT,
        priority TEXT DEFAULT 'P1',
        artifact_url TEXT,
        status TEXT DEFAULT 'Active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS modules (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        parent_module_id TEXT,
        owner_res_id TEXT NOT NULL,
        knowledge_base TEXT,
        layer_type TEXT,
        entity_type TEXT DEFAULT 'Code',
        status TEXT DEFAULT 'Active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_module_id) REFERENCES modules(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS resources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        dingtalk_id TEXT,
        professional_skill TEXT,
        org_role TEXT NOT NULL,
        weekly_capacity INT DEFAULT 40,
        status TEXT DEFAULT 'Available',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        activity_id TEXT,
        module_id TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        module_iteration_goal TEXT NOT NULL,
        estimated_days REAL,
        status TEXT DEFAULT 'Todo',
        depends_on TEXT,
        start_date TEXT,
        due_date TEXT,
        artifact_url TEXT,
        redmine_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects(id),
        FOREIGN KEY (activity_id) REFERENCES activities(id),
        FOREIGN KEY (module_id) REFERENCES modules(id),
        FOREIGN KEY (resource_id) REFERENCES resources(id)
    )''')

    conn.commit()
    conn.close()
    print(f"Successfully initialized {DB_PATH} with refined schema.")

if __name__ == "__main__":
    main()
