import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Only default to smart_task_test if no DB_NAME is provided in the environment
if not os.getenv("DB_NAME"):
    os.environ["DB_NAME"] = "smart_task_test"
print(f">>> [conftest] Using DB_NAME: {os.environ.get('DB_NAME')}")

# Import from src ONLY after env vars are set
from src.task_management.db import get_db_connection

@pytest.fixture(scope="session", autouse=True)
def cleanup_stale_connections():
    """Forcefully terminate any lingering database connections before the test session starts."""
    db_name = os.getenv("DB_NAME", "smart_task_test")
    try:
        # Connect to 'postgres' management DB to perform the termination
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            user=os.getenv("DB_USER", "smart_user"),
            password=os.getenv("DB_PASSWORD", "smart_pass"),
            dbname="postgres"
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{db_name}' AND pid <> pg_backend_pid();")
        conn.close()
    except Exception as e:
        print(f"\n>>> [conftest] Warning: Could not cleanup stale connections: {e}")

@pytest.fixture(scope="session")
def db_conn():
    """Create a session-wide database connection."""
    conn = get_db_connection()
    yield conn
    conn.close()

@pytest.fixture
def db_cursor(db_conn):
    """Provide a clean cursor for each test, using a transaction and rolling back."""
    # Note: Rolling back is a common TDD pattern, but since the user said 
    # "it's simple" and might want to see data, we'll decide whether to rollback.
    # For now, let's just provide a normal cursor.
    with db_conn.cursor(cursor_factory=RealDictCursor) as cursor:
        yield cursor
        db_conn.rollback() # Rollback by default to keep the test DB clean

@pytest.fixture(autouse=True)
def anyio_backend():
    return 'asyncio'
