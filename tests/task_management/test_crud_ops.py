import pytest
import uuid
import json
from src.task_management.tools import (
    query_sql, 
    upsert_resource, 
    upsert_project, 
    upsert_activity, 
    upsert_module, 
    upsert_task,
    delete_record
)
from src.task_management.db import execute_mutation

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
    results = json.loads(results_json)
    db_name = results[0]["current_database"]
    print(f"\n>>> Active DB: {db_name}")
    assert db_name == "smart_task_test"

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
        agent_dir="smart_task_app/agents/coder",
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
    assert results[0]["agent_dir"] == "smart_task_app/agents/coder"

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
        project_id=project_id,
        module_id=module_id,
        module_name="Test Module",
        resource_id=resource_id,
        resource_name="Chain Owner",
        module_iteration_goal="Complete TDD setup"
    )
    # The return strings in new tools changed slightly, mostly "Successfully processed..."
    assert "Successfully processed" in msg_tsk
    
    # 5. Verify task relationship
    results = json.loads(query_sql(f"SELECT * FROM tasks WHERE id = '{task_id}'"))
    assert results[0]["module_id"] == module_id
    assert results[0]["project_id"] == project_id
