$env:PYTHONPATH = ".;$env:PYTHONPATH"
$env:ENABLE_A2A = "true"
# 默认端口 8000，可以通过 --port 修改
adk api-server smart_task_app --a2a --port 8000
