#Requires -Version 5.1
<#
.SYNOPSIS
    One-command startup for Macro Terminal dashboard.
    Usage: .\run.ps1  (or: .\run.ps1 -Reset to wipe data and start fresh)
#>

param(
    [switch]$Reset,
    [switch]$Logs,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Write-Step($n, $msg) {
    Write-Host "`n[$n] $msg" -ForegroundColor Cyan
}
function Write-Ok($msg) {
    Write-Host "    OK  $msg" -ForegroundColor Green
}
function Write-Warn($msg) {
    Write-Host "    !!  $msg" -ForegroundColor Yellow
}
function Write-Fail($msg) {
    Write-Host "    ERR $msg" -ForegroundColor Red
}

# ── Stop mode ───────────────────────────────────────────────────────────────
if ($Stop) {
    Write-Host "`nStopping all services..." -ForegroundColor Yellow
    Set-Location $ProjectRoot
    docker compose down
    Write-Host "Stopped." -ForegroundColor Green
    exit 0
}

# ── Logs mode ────────────────────────────────────────────────────────────────
if ($Logs) {
    Set-Location $ProjectRoot
    docker compose logs -f backend celery_worker seeder
    exit 0
}

Write-Host @"

  ╔══════════════════════════════════════════════╗
  ║       MACRO TERMINAL  —  Local Startup       ║
  ╚══════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# ── Check Docker Desktop ─────────────────────────────────────────────────────
Write-Step "1/5" "Checking Docker Desktop..."
try {
    $null = docker info 2>&1
    Write-Ok "Docker is running"
} catch {
    Write-Fail "Docker Desktop is not running."
    Write-Host "       Please start Docker Desktop and re-run this script." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Optional: wipe volumes ───────────────────────────────────────────────────
Set-Location $ProjectRoot
if ($Reset) {
    Write-Warn "Reset mode: removing volumes..."
    docker compose down -v 2>&1 | Out-Null
    Write-Ok "Volumes cleared"
}

# ── Start Docker services ────────────────────────────────────────────────────
Write-Step "2/5" "Building and starting Docker services..."
Write-Host "    (This may take 2-3 min on first run while images build)" -ForegroundColor DarkGray

docker compose up -d --build 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Fail "docker compose up failed. Check Docker Desktop."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Docker services started"

# ── Wait for backend health ──────────────────────────────────────────────────
Write-Step "3/5" "Waiting for backend API to become healthy..."
$maxAttempts = 60
$attempt = 0
$ready = $false

while ($attempt -lt $maxAttempts) {
    $attempt++
    Start-Sleep -Seconds 3
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:8000/health" -TimeoutSec 3 -ErrorAction Stop
        if ($resp.status -eq "ok") {
            $ready = $true
            break
        }
    } catch { }
    Write-Host "    . waiting ($($attempt * 3)s / $($maxAttempts * 3)s max)" -ForegroundColor DarkGray
}

if (-not $ready) {
    Write-Fail "Backend did not become healthy in time."
    Write-Warn "Check logs: docker compose logs backend"
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Ok "Backend healthy at http://localhost:8000"
Write-Ok "API docs:          http://localhost:8000/docs"

# ── Data seeding check ───────────────────────────────────────────────────────
Write-Step "4/5" "Checking data seeding status..."
Write-Host "    (The seeder container runs automatically in the background)" -ForegroundColor DarkGray

# Show seeder logs briefly
$seederRunning = docker compose ps seeder 2>&1 | Select-String "running|exited"
if ($seederRunning) {
    Write-Ok "Seeder is active — data will appear in 2-3 minutes"
} else {
    Write-Warn "Seeder status unknown — you can re-trigger manually:"
    Write-Host "    curl http://localhost:8000/api/trigger/backfill" -ForegroundColor DarkGray
}

# ── Frontend ─────────────────────────────────────────────────────────────────
Write-Step "5/5" "Checking frontend..."

# Check if frontend is in Docker
$frontendContainer = docker ps --filter "name=macro_frontend" --format "{{.Names}}" 2>&1
if ($frontendContainer -match "macro_frontend") {
    Write-Ok "Frontend running in Docker at http://localhost:3000"
} else {
    Write-Warn "Frontend not in Docker — check container startup or wait 30s"
    Write-Host "    To run frontend locally instead:" -ForegroundColor DarkGray
    Write-Host "    cd frontend; npm run dev" -ForegroundColor DarkGray
}

# ── Open browser ─────────────────────────────────────────────────────────────
Write-Host ""
$waitFrontend = 0
Write-Host "    Waiting for frontend to be ready..." -ForegroundColor DarkGray
while ($waitFrontend -lt 30) {
    Start-Sleep -Seconds 3
    $waitFrontend += 3
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:3000" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        break
    } catch { }
    Write-Host "    . $waitFrontend`s" -ForegroundColor DarkGray
}

Start-Process "http://localhost:3000"

Write-Host @"

  ╔══════════════════════════════════════════════╗
  ║   Dashboard: http://localhost:3000           ║
  ║   API Docs:  http://localhost:8000/docs      ║
  ║   Health:    http://localhost:8000/health    ║
  ╠══════════════════════════════════════════════╣
  ║  NOTE: Charts fill up within 2-3 min as      ║
  ║  background tasks fetch & store data.        ║
  ╠══════════════════════════════════════════════╣
  ║  .\run.ps1 -Stop    Stop all services        ║
  ║  .\run.ps1 -Logs    Tail backend logs        ║
  ║  .\run.ps1 -Reset   Wipe data & restart      ║
  ╚══════════════════════════════════════════════╝
"@ -ForegroundColor Green
