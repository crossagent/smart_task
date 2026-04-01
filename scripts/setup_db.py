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
    cursor.execute('''CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT,
        memo_content TEXT,
        category TEXT,
        priority TEXT,
        due_date TEXT,
        origin_id TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS features (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        event_id TEXT,
        owner TEXT,
        collaborators TEXT,
        status TEXT,
        origin_id TEXT,
        FOREIGN KEY (event_id) REFERENCES events(id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS modules (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT,
        owner_id TEXT,
        description TEXT,
        type TEXT,
        origin_id TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS resources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        weekly_capacity REAL,
        status TEXT,
        skills TEXT,
        origin_id TEXT
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        event_id TEXT,
        feature_id TEXT,
        module_id TEXT,
        resource_id TEXT,
        target_state TEXT,
        estimated_hours REAL,
        status TEXT,
        depends_on TEXT,
        due_date TEXT,
        origin_id TEXT,
        FOREIGN KEY (event_id) REFERENCES events(id),
        FOREIGN KEY (feature_id) REFERENCES features(id),
        FOREIGN KEY (module_id) REFERENCES modules(id),
        FOREIGN KEY (resource_id) REFERENCES resources(id)
    )''')

    conn.commit()
    conn.close()
    print(f"Successfully initialized {DB_PATH} with refined schema.")

if __name__ == "__main__":
    main()
