$env:PYTHONPATH = ".;$env:PYTHONPATH"
$env:ENABLE_A2A = "true"
adk api_server smart_task_app/remote_a2a --a2a --port 8000
