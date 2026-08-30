﻿﻿﻿# 一键启动全部服务：后端(8000) + 管理后台(3000) + C端商城(3001)
# 用法：右键 → "使用 PowerShell 运行"，或在终端中执行 .\start_all.ps1

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodePath = "C:\Program Files\nodejs"
$logDir = "$projectRoot\logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ── Redis 启动（本地版，先于后端就绪）──
function Ensure-Redis {
    $redisPort = 6379
    $redisExe = Join-Path $projectRoot ".venv\redis\redis-server.exe"
    # 已在监听则跳过
    if (Get-NetTCPConnection -State Listen -LocalPort $redisPort -ErrorAction SilentlyContinue) {
        Write-Host "  Redis already running on $redisPort" -ForegroundColor Green
        return $true
    }
    if (-not (Test-Path $redisExe)) {
        Write-Host "  WARNING: 未找到 $redisExe，本地 Redis 未安装，跳过启动" -ForegroundColor Yellow
        return $false
    }
    Write-Host "  Starting local Redis ($redisExe)..." -ForegroundColor Yellow
    Start-Process -FilePath $redisExe -ArgumentList "--port", "$redisPort" -WindowStyle Hidden
    for ($i = 0; $i -lt 15; $i++) {
        if (Get-NetTCPConnection -State Listen -LocalPort $redisPort -ErrorAction SilentlyContinue) {
            Write-Host "  Redis started (local redis-server)" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }
    Write-Host "  WARNING: Redis 启动后端口未就绪，请检查 $redisExe" -ForegroundColor Yellow
    return $false
}

# 启动后端 (嵌入模型+LLM自动拉起，需要约30-60秒)
$backendLog = "$logDir\backend.log"
Start-Job -Name "backend" -ArgumentList $projectRoot, $backendLog {
    param($root, $log)
    Set-Location $root
    & "$root\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 *>> $log
}

# 启动管理后台 (3000)
Start-Job -Name "admin" -ArgumentList $projectRoot, $nodePath {
    param($root, $np)
    $env:Path = "$np;$env:Path"
    Set-Location "$root\web\admin"
    & "$np\npx.cmd" vite --host 2>&1 | Out-Null
}

# 启动C端商城 (3001)
Start-Job -Name "shop" -ArgumentList $projectRoot, $nodePath {
    param($root, $np)
    $env:Path = "$np;$env:Path"
    Set-Location "$root\web\shop"
    & "$np\npx.cmd" vite --host 2>&1 | Out-Null
}

Write-Host ""
Write-Host "  Starting services..." -ForegroundColor Yellow

# 先确保 Redis 就绪（后端依赖）
Ensure-Redis | Out-Null

# 等待后端就绪（最多等120秒）
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient("127.0.0.1", 8000)
        $c.Close()
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

if (-not $ready) {
    Write-Host "  Backend failed to start. Check: $backendLog" -ForegroundColor Red
} else {
    Write-Host ""
    Write-Host "  All services started:" -ForegroundColor Green
    Write-Host "    Backend API -> http://localhost:8000/docs" -ForegroundColor White
    Write-Host "    Admin Panel -> http://localhost:3000" -ForegroundColor Cyan
    Write-Host "    Shop        -> http://localhost:3001" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "  Press Enter to stop all services..." -ForegroundColor Yellow

Read-Host
Get-Job | Stop-Job
Get-Job | Remove-Job
# 清理残留的 LLM 子进程
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Write-Host "  All services stopped" -ForegroundColor Gray
