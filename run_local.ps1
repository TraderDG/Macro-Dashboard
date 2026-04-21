# Macro Terminal — Local Startup Script
# Usage: .\run_local.ps1
# Opens backend on :8001 and frontend on :3000

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

function Kill-Port($port) {
    $pids = netstat -ano | Select-String ":$port\s.*LISTENING" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    foreach ($p in $pids) {
        if ($p -and $p -match '^\d+$') {
            try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

Write-Host "[1/4] Stopping any existing servers..." -ForegroundColor Cyan
Kill-Port 8001
Kill-Port 3000
Start-Sleep 1

Write-Host "[2/4] Starting backend (FastAPI + SQLite) on :8001..." -ForegroundColor Cyan
$backendLog = Join-Path $root "backend_run.log"
$backendProc = Start-Process python -ArgumentList "-m uvicorn main_local:app --port 8001" `
    -WorkingDirectory $backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLog `
    -PassThru
Write-Host "   Backend PID: $($backendProc.Id)"

Write-Host "[3/4] Waiting for backend to start..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep 2
    try {
        $resp = Invoke-WebRequest "http://localhost:8001/health" -TimeoutSec 2 -UseBasicParsing 2>$null
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if (-not $ready) { Write-Host "Backend may not be ready — check backend_run.log" -ForegroundColor Yellow }
else { Write-Host "   Backend ready!" -ForegroundColor Green }

Write-Host "[4/4] Starting frontend (Next.js) on :3000..." -ForegroundColor Cyan
$frontendLog = Join-Path $root "frontend_run.log"
$frontendProc = Start-Process npm -ArgumentList "run dev" `
    -WorkingDirectory $frontend `
    -WindowStyle Hidden `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError $frontendLog `
    -PassThru
Write-Host "   Frontend PID: $($frontendProc.Id)"

Start-Sleep 5
Write-Host ""
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Write-Host "  Macro Terminal running:" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8001" -ForegroundColor Green
Write-Host "  API docs: http://localhost:8001/docs" -ForegroundColor Green
Write-Host "═══════════════════════════════════════" -ForegroundColor Green
Start-Process "http://localhost:3000"
