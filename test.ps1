# Smart Task TDD Script
# Usage: .\test.ps1

$env:DB_NAME = "smart_task_test"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5433"
$env:DB_USER = "smart_user"
$env:DB_PASSWORD = "smart_pass"

Write-Host ">>> Running Smart Task MCP Engine Tests [DB: $env:DB_NAME]..." -ForegroundColor Cyan

# Run pytest with -s (show stdout) and -v (verbose)
uv run pytest -s -v tests/test_mcp_ops.py
