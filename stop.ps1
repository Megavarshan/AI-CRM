<#
  Orbit — stop all local dev services started by start.ps1.
  Kills whatever is listening on the Orbit ports (and their parent windows),
  plus the Celery workers (which have no listening port).

  Usage:  powershell -ExecutionPolicy Bypass -File .\stop.ps1
#>

$ports = @(3000, 8000, 8001, 6379)

foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($pid_ in ($conns.OwningProcess | Select-Object -Unique)) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid_" -ErrorAction SilentlyContinue
        if ($proc -and $proc.ParentProcessId) {
            Stop-Process -Id $proc.ParentProcessId -Force -ErrorAction SilentlyContinue
        }
        Stop-Process -Id $pid_ -Force -ErrorAction SilentlyContinue
        Write-Host "stopped listener on port $p (pid $pid_)" -ForegroundColor Yellow
    }
}

# Celery workers (no listening socket) — match by command line.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'celery -A celery_app' } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "stopped celery worker (pid $($_.ProcessId))" -ForegroundColor Yellow
    }

Write-Host "`nOrbit services stopped." -ForegroundColor Green
