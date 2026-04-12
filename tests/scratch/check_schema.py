import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def check_schema():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5433"),
        dbname=os.getenv("DB_NAME", "smart_task_hub"),
        user=os.getenv("DB_USER", "smart_user"),
        password=os.getenv("DB_PASSWORD", "smart_pass")
    )
    cur = conn.cursor()
    
    tables = ['tasks', 'modules', 'resources']
    for table in tables:
        print(f"\n--- Columns in {table} ---")
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
        for col in cur.fetchall():
            print(f"  {col[0]} ({col[1]})")
            
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_schema()
