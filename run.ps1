# Self-Healing Infrastructure - Windows Startup Helper
param (
    [switch]$LocalStandalone,
    [switch]$Docker
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   SELF-HEALING INFRASTRUCTURE WITH ANSIBLE & PROMETHEUS  " -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

if ($LocalStandalone) {
    Write-Host "[INFO] Starting local standalone Python FastAPI control plane..." -ForegroundColor Yellow
    python -m pip install -r backend/requirements.txt
    python backend/main.py
    exit 0
}

Write-Host "[1/3] Checking Docker daemon status..." -ForegroundColor Yellow
$dockerCheck = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[NOTICE] Docker Desktop daemon is not responding yet." -ForegroundColor DarkYellow
    Write-Host "Please make sure Docker Desktop is launched on Windows." -ForegroundColor DarkYellow
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "1. Launch Docker Desktop from your Windows Start Menu, then re-run: .\run.ps1" -ForegroundColor White
    Write-Host "2. Or run in local standalone demo mode right now: .\run.ps1 -LocalStandalone" -ForegroundColor Green
    Write-Host ""
    exit 1
}

Write-Host "[2/3] Building and starting Docker Compose services..." -ForegroundColor Yellow
docker compose up -d --build

Write-Host ""
Write-Host "[3/3] Verifying container cluster status..." -ForegroundColor Yellow
docker compose ps

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  INFRASTRUCTURE IS ONLINE AND ACTIVELY MONITORED!        " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Dashboard URL:          http://localhost:8000" -ForegroundColor Cyan
Write-Host "NGINX Target Service:   http://localhost:8080" -ForegroundColor Cyan
Write-Host "Prometheus Metrics:     http://localhost:9090" -ForegroundColor Cyan
Write-Host "Alertmanager Alerts:    http://localhost:9093" -ForegroundColor Cyan
Write-Host "Node Exporter Metrics:  http://localhost:9100/metrics" -ForegroundColor Cyan
Write-Host "Blackbox Exporter:      http://localhost:9115" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
