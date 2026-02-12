$env:PYTHONPATH = ".;$env:PYTHONPATH"
$env:ENABLE_A2A = "true"

# Start Remote Agents in a new window
Write-Host "Starting Remote Agents (Port 8000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& { $env:PYTHONPATH='.;$env:PYTHONPATH'; $env:ENABLE_A2A='true'; adk api_server smart_task_app/remote_a2a --a2a --port 8000 }"

# Wait a moment for them to initialize
Start-Sleep -Seconds 2

# Start Root Agent in current window
Write-Host "Starting Root Agent Web UI..."
adk web smart_task_app
