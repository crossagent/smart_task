# Smart Task Domain-Driven Module Test Script
# Usage: .\test.ps1

$env:DB_NAME = "smart_task_test"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5433"
$env:DB_USER = "smart_user"
$env:DB_PASSWORD = "smart_pass"

$modules = @(
    "mcp_server",
    "task_management",
    "task_execution",
    "architect_agent",
    "coder_agent"
)

Write-Host ">>> Running Smart Task Engine Tests across all domains [DB: $env:DB_NAME]..." -ForegroundColor Cyan

foreach ($module in $modules) {
    if (Test-Path "tests\$module") {
        Write-Host "`n>>> [Testing] Module: $module" -ForegroundColor Green
        uv run pytest -s -v tests/$module
    } else {
        Write-Host "`n>>> [Skipped] No tests found for Module: $module" -ForegroundColor Yellow
    }
}
