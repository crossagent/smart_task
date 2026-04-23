import pytest
import uuid
import json
from src.tools import (
    query_sql, 
    get_task_context,
    upsert_resource, 
    upsert_project, 
    upsert_activity, 
    upsert_module, 
    upsert_task,
    delete_record
)
from src.db import execute_mutation, execute_query

@pytest.fixture
def resource_id():
    return f"RES-TEST-{uuid.uuid4().hex[:8]}"

@pytest.fixture
def project_id():
    return f"PRJ-TEST-{uuid.uuid4().hex[:8]}"

@pytest.fixture
def module_id():
    return f"MOD-TEST-{uuid.uuid4().hex[:8]}"

def test_db_connection():
    """Verify that we are indeed connected to the test database."""
    results_json = query_sql("SELECT current_database();")
    # If the database connection fails, query_sql returns an error string
    # We should catch this to provide a better error message in tests
    try:
        results = json.loads(results_json)
    except json.JSONDecodeError:
        pytest.fail(f"Database connection test failed. Tool output: {results_json}")
        
    db_name = results[0]["current_database"]
    print(f"\n>>> Active DB: {db_name}")
    assert "smart_task" in db_name

def test_query_sql_validation():
    """Verify that query_sql only allows SELECT."""
    result = query_sql("DROP TABLE resources;")
    assert "Only read-only queries" in result

def test_resource_upsert_and_query(resource_id):
    """Test creating a resource and querying it."""
    # 1. Upsert
    msg = upsert_resource(
        id=resource_id,
        name="Test User",
        resource_type="coder",
        agent_dir="src/agents/coder",
        org_role="Tester",
        weekly_capacity=40
    )
    assert "Successfully processed" in msg
    
    # 2. Query via SQL
    sql = f"SELECT * FROM resources WHERE id = '{resource_id}'"
    results_json = query_sql(sql)
    
    try:
        results = json.loads(results_json)
    except json.JSONDecodeError:
        pytest.fail(f"Expected JSON from query_sql, but got: {results_json}")
    
    assert len(results) == 1
    assert results[0]["name"] == "Test User"
    assert results[0]["org_role"] == "Tester"

def test_full_chain_upsert(resource_id, project_id, module_id):
    """Test a full chain of dependencies (Resource -> Project -> Module -> Task)."""
    # 1. Resource
    upsert_resource(id=resource_id, name="Chain Owner", org_role="Architect")
    
    # 2. Project
    msg_prj = upsert_project(
        id=project_id,
        name="Test Chain Project",
        owner_res_id=resource_id,
        memo_content="Testing dependencies"
    )
    assert "Successfully processed" in msg_prj
    
    # 3. Module
    msg_mod = upsert_module(
        id=module_id,
        project_id=project_id,
        name="Test Module",
        owner_res_id=resource_id
    )
    assert "Successfully processed" in msg_mod
    
    # 4. Task
    task_id = f"TSK-TEST-{uuid.uuid4().hex[:8]}"
    msg_tsk = upsert_task(
        id=task_id,
        module_id=module_id,
        module_name="Test Module",
        resource_id=resource_id,
        resource_name="Chain Owner",
        module_iteration_goal="Complete TDD setup"
    )
    assert "Successfully processed" in msg_tsk
    
    # 5. Verify task relationship
    results_json = query_sql(f"SELECT * FROM tasks WHERE id = '{task_id}'")
    results = json.loads(results_json)
    assert results[0]["module_id"] == module_id

def test_custom_json_encoder():
    """Verify that datetime and decimal are correctly encoded in query_sql."""
    sql = "SELECT CURRENT_TIMESTAMP as now, 123.45::numeric as val"
    results_json = query_sql(sql)
    results = json.loads(results_json)
    
    assert "now" in results[0]
    assert isinstance(results[0]["now"], str) # ISO format string
    assert results[0]["val"] == 123.45

def test_task_context_resolution(resource_id, project_id, module_id):
    """Verify that get_task_context returns full joined information."""
    # 1. Setup chain
    upsert_resource(id=resource_id, name="Context King", org_role="Architect")
    upsert_project(id=project_id, name="Context Project", owner_res_id=resource_id)
    upsert_module(id=module_id, project_id=project_id, name="Context Module", owner_res_id=resource_id)
    
    task_id = f"TSK-CTX-{uuid.uuid4().hex[:8]}"
    upsert_task(
        id=task_id,
        module_id=module_id,
        module_name="Context Module",
        resource_id=resource_id,
        resource_name="Context King",
        module_iteration_goal="Test context join"
    )
    
    # 2. Get Context
    context_json = get_task_context(task_id)
    try:
        ctx = json.loads(context_json)
    except json.JSONDecodeError:
        pytest.fail(f"get_task_context failed. Output: {context_json}")
    
    assert ctx["task_id"] == task_id
    assert ctx["project_name"] == "Context Project"
    assert ctx["module_name"] == "Context Module"

def test_upsert_atomic_conflict(resource_id, module_id):
    """Verify that multiple upserts to the same ID update fields correctly."""
    upsert_resource(id=resource_id, name="Conflict Hero", org_role="Coder")
    upsert_module(id=module_id, project_id="NONE", name="Conflict Mod", owner_res_id=resource_id)
    
    task_id = f"TSK-CONFLICT-{uuid.uuid4().hex[:8]}"
    
    # First Upsert
    upsert_task(
        id=task_id, module_id=module_id, module_name="M1", 
        resource_id=resource_id, resource_name="R1",
        module_iteration_goal="Goal 1", status="pending"
    )
    
    # Second Upsert (Update status and goal)
    upsert_task(
        id=task_id, module_id=module_id, module_name="M1", 
        resource_id=resource_id, resource_name="R1",
        module_iteration_goal="Goal 2", status="ready"
    )
    
    # Verify values
    results_json = query_sql(f"SELECT * FROM tasks WHERE id = '{task_id}'")
    results = json.loads(results_json)
    assert results[0]["module_iteration_goal"] == "Goal 2"
    assert results[0]["status"] == "ready"
