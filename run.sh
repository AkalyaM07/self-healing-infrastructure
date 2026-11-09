#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "   SELF-HEALING INFRASTRUCTURE WITH ANSIBLE & PROMETHEUS  "
echo "=========================================================="

echo "[1/3] Checking Docker daemon status..."
if ! docker info > /dev/null 2>&1; then
    echo "[ERROR] Docker is not running. Please start Docker service first."
    exit 1
fi

echo "[2/3] Building and starting all Docker Compose services..."
docker compose up -d --build

echo ""
echo "[3/3] Checking service status..."
docker compose ps

echo ""
echo "=========================================================="
echo "  INFRASTRUCTURE IS ONLINE AND ACTIVELY MONITORED!        "
echo "=========================================================="
echo "Dashboard URL:          http://localhost:8000"
echo "NGINX Target Service:   http://localhost:8080"
echo "Prometheus Metrics:     http://localhost:9090"
echo "Alertmanager Alerts:    http://localhost:9093"
echo "Node Exporter Metrics:  http://localhost:9100/metrics"
echo "Blackbox Exporter:      http://localhost:9115"
echo "=========================================================="
