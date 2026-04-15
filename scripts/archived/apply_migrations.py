import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.task_management.db import execute_mutation

migrations = [
    # 1. Drop old column and add new ones
    "ALTER TABLE tasks DROP COLUMN IF EXISTS estimated_days",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS estimated_hours DECIMAL(10,2) DEFAULT NULL",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS blocker_reason TEXT DEFAULT NULL",
    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS retry_count INT DEFAULT 0",
    
    # 2. Create Dynamic Views
    """
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
    """,
    """
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
    """
]

print("Applying DB migrations to current database...")
for m in migrations:
    try:
        execute_mutation(m)
        print("Success:", m.split('\\n')[0][:50])
    except Exception as e:
        print("Error/Skip:", e)
print("Migration script completed.")
