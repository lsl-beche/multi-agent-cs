# 启动 CSagent 后端 (端口 8000)
# 用法：右键此文件 → "使用 PowerShell 运行"，或在终端中执行 .\start_backend.ps1

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& "$projectRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
