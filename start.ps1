<#
  Orbit — local dev launcher (Windows, no Docker).

  Starts all 5 services, each in its own titled PowerShell window so you can
  watch logs and Ctrl+C them individually:
    - Redis            (portable, .redis\redis-server.exe)  :6379
    - Channel worker   (Celery)
    - Channel API      (uvicorn)                            :8001
    - CRM worker       (Celery)
    - CRM API          (uvicorn)                            :8000
    - Frontend         (next dev)                           :3000

  Usage:   powershell -ExecutionPolicy Bypass -File .\start.ps1
  Stop:    powershell -ExecutionPolicy Bypass -File .\stop.ps1
#>

$ErrorActionPreference = "Stop"
$root  = $PSScriptRoot
$crmPy = Join-Path $root "crm\venv\Scripts\python.exe"
$chPy  = Join-Path $root "channel\venv\Scripts\python.exe"
$redis = Join-Path $root ".redis\redis-server.exe"

# Use whichever shell is running this script (pwsh.exe or powershell.exe),
# falling back to Windows PowerShell by name.
$Shell = (Get-Process -Id $PID).Path
if (-not $Shell) { $Shell = "powershell.exe" }

function Test-Port($p) {
    [bool](Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue)
}

function Start-Svc($title, $cwd, $cmd) {
    $inner = "`$host.UI.RawUI.WindowTitle='$title'; Set-Location '$cwd'; $cmd"
    Start-Process $Shell -ArgumentList "-NoExit", "-Command", $inner | Out-Null
    Write-Host "  started: $title" -ForegroundColor Green
}

# --- sanity checks ---------------------------------------------------------
foreach ($p in @($crmPy, $chPy, $redis)) {
    if (-not (Test-Path $p)) {
        Write-Host "Missing: $p" -ForegroundColor Red
        Write-Host "Run setup first (create venvs / download Redis). See docs/DEVELOPMENT.md." -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`nStarting Orbit services..." -ForegroundColor Cyan

# --- Redis (only if not already listening) ---------------------------------
if (Test-Port 6379) {
    Write-Host "  Redis already running on 6379 (skipping)" -ForegroundColor DarkGray
} else {
    Start-Svc "Orbit Redis" "$root\.redis" "& '$redis' --port 6379 --save '' --appendonly no"
    Start-Sleep -Seconds 1
}

# --- Channel service -------------------------------------------------------
Start-Svc "Orbit Channel Worker" "$root\channel" "& '$chPy' -m celery -A celery_app worker -Q channel -P threads -c 8 --loglevel=info"
Start-Svc "Orbit Channel API"    "$root\channel" "& '$chPy' -m uvicorn main:app --host 0.0.0.0 --port 8001"

# --- CRM service -----------------------------------------------------------
Start-Svc "Orbit CRM Worker" "$root\crm" "& '$crmPy' -m celery -A celery_app worker -Q crm -P threads -c 8 --loglevel=info"
Start-Svc "Orbit CRM API"    "$root\crm" "& '$crmPy' -m uvicorn main:app --host 0.0.0.0 --port 8000"

# --- Frontend --------------------------------------------------------------
Start-Svc "Orbit Frontend" "$root\frontend" "npm run dev"

# --- wait for health -------------------------------------------------------
Write-Host "`nWaiting for services to come up..." -ForegroundColor Cyan
$ok = $false
foreach ($i in 1..30) {
    Start-Sleep -Seconds 2
    $crm  = Test-Port 8000
    $chan = Test-Port 8001
    $web  = Test-Port 3000
    if ($crm -and $chan -and $web) { $ok = $true; break }
}

Write-Host ""
if ($ok) {
    Write-Host "All services are up." -ForegroundColor Green
} else {
    Write-Host "Some services did not report ready in time — check their windows." -ForegroundColor Yellow
}
Write-Host "  Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "  CRM API  : http://localhost:8000/health" -ForegroundColor White
Write-Host "  Channel  : http://localhost:8001/health" -ForegroundColor White
Write-Host "`nTo stop everything:  powershell -ExecutionPolicy Bypass -File .\stop.ps1`n" -ForegroundColor DarkGray
