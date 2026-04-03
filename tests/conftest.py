import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Force DB_NAME to smart_task_test if it's not already set
# This ensures we don't accidentally run tests against the prod/dev DB
if os.getenv("DB_NAME") != "smart_task_test":
    os.environ["DB_NAME"] = "smart_task_test"
print(f">>> [conftest] Using DB_NAME: {os.environ.get('DB_NAME')}")

# Import from main ONLY after env vars are set
from main import get_db_connection

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
