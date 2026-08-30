# 同时启动管理后台 (3000) 和 C端商城 (3001)
# 用法：右键此文件 → "使用 PowerShell 运行"，或在终端中执行 .\start_frontend.ps1

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodePath = "C:\Program Files\nodejs"
$env:Path = "$nodePath;$env:Path"

# 启动管理后台 (端口 3000)
$adminJob = Start-Job -Name "admin" -ArgumentList $projectRoot, $nodePath {
    param($root, $np)
    $env:Path = "$np;$env:Path"
    Set-Location "$root\web\admin"
    & "$np\npx.cmd" vite --host
}

# 启动 C端商城 (端口 3001)
$shopJob = Start-Job -Name "shop" -ArgumentList $projectRoot, $nodePath {
    param($root, $np)
    $env:Path = "$np;$env:Path"
    Set-Location "$root\web\shop"
    & "$np\npx.cmd" vite --host
}

Write-Host " 管理后台  →  http://localhost:3000" -ForegroundColor Cyan
Write-Host " C端商城  →  http://localhost:3001" -ForegroundColor Cyan
Write-Host " 按 Enter 停止所有前端服务..." -ForegroundColor Yellow

# 等待用户按 Enter 后停止
Read-Host
Stop-Job -Name "admin"
Stop-Job -Name "shop"
Remove-Job -Name "admin"
Remove-Job -Name "shop"
Write-Host " 前端服务已停止" -ForegroundColor Gray
