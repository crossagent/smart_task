$env:PYTHONPATH = ".;$env:PYTHONPATH"
# 默认端口 8000，可以通过 --port 修改
adk api-server smart_task_app --port 8000
