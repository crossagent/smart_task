import sqlite3
import pprint

db_path = r'D:\MyProject\smart_task\archive\migration_v13\smart_task.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]

schema = {}
for table in tables:
    cursor.execute(f"PRAGMA table_info({table});")
    schema[table] = cursor.fetchall()

pprint.pprint(schema)
conn.close()
