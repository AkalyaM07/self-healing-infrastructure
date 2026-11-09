import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import (
    init_db,
    get_all_alerts,
    get_all_recovery_history,
    get_all_activity,
    get_recovery_statistics,
    log_activity
)
from monitoring import (
    check_nginx_http_status,
    get_current_metrics,
    get_live_alerts_from_alertmanager,
    last_health_check_time,
    last_failure_time
)
from webhook import process_alertmanager_webhook, execute_ansible_playbook

app = FastAPI(
    title="Self-Healing Infrastructure Webhook & Monitoring API",
    version="1.0.0",
    description="Real-time DevOps self-healing control plane integrating Prometheus, Alertmanager, and Ansible."
)

# Enable CORS for local web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.getenv("FRONTEND_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend"))

@app.on_event("startup")
def on_startup():
    init_db()
    print("[SYSTEM] Self-Healing Database initialized.")

# Mount static frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Self-Healing Infrastructure API Running</h1><p>Frontend directory not found.</p>")

@app.get("/api/health")
def get_health():
    return {
        "status": "healthy",
        "service": "Self-Healing Infrastructure Backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "SQLite connected",
        "playbook_available": os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), "ansible", "restart_nginx.yml"))
    }

@app.get("/api/metrics")
def get_metrics():
    metrics = get_current_metrics()
    return metrics

@app.get("/api/server-status")
def get_server_status():
    nginx_health = check_nginx_http_status()
    metrics = get_current_metrics()
    stats = get_recovery_statistics()

    is_healthy = nginx_health["is_healthy"]
    
    infra_status = "HEALTHY" if is_healthy else "DEGRADED"
    nginx_status = "RUNNING" if is_healthy else "STOPPED"
    server_status = "ONLINE"

    return {
        "infrastructure_status": infra_status,
        "server_status": server_status,
        "nginx_status": nginx_status,
        "nginx_http_code": nginx_health.get("status_code"),
        "nginx_health_source": nginx_health.get("source"),
        "cpu_percent": metrics["current_cpu"],
        "memory_percent": metrics["current_memory"],
        "disk_percent": metrics["current_disk"],
        "website_available": is_healthy,
        "last_health_check": last_health_check_time,
        "last_failure_time": last_failure_time,
        "total_alerts": stats["total_alerts"],
        "successful_recoveries": stats["successful_recoveries"],
        "failed_recoveries": stats["failed_recoveries"]
    }

@app.get("/api/alerts")
def get_alerts():
    # Retrieve persisted alerts from SQLite
    db_alerts = get_all_alerts(limit=50)
    # Check live Alertmanager alerts
    live_alerts = get_live_alerts_from_alertmanager()
    
    return {
        "live_alerts": live_alerts,
        "history_alerts": db_alerts
    }

@app.get("/api/recovery-history")
def get_recovery_history():
    history = get_all_recovery_history(limit=50)
    return history

@app.get("/api/activity")
def get_activity():
    activity = get_all_activity(limit=50)
    return activity

@app.post("/webhook/alerts")
async def alertmanager_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    result = process_alertmanager_webhook(payload)
    return JSONResponse(status_code=200, content=result)

# Simulation & Demonstration endpoints for internship evaluation / live testing
@app.post("/api/simulate/stop-nginx")
def simulate_stop_nginx():
    """Simulate NGINX crash or failure by stopping the NGINX container."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise HTTPException(status_code=500, detail="Docker CLI is not found on host to stop container.")

    try:
        res = subprocess.run([docker_bin, "stop", "nginx"], capture_output=True, text=True, timeout=15)
        log_activity(
            event_type="FAILURE_SIMULATION",
            title="Manual Failure Simulation Initiated",
            description="Operator manually stopped NGINX container to trigger Blackbox exporter alert rule.",
            badge_color="red"
        )
        return {
            "status": "success",
            "message": "NGINX container stopped. Blackbox exporter will detect failure and Alertmanager will trigger Ansible recovery.",
            "output": res.stdout.strip()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop NGINX container: {str(e)}")

@app.post("/api/simulate/start-nginx")
def simulate_start_nginx():
    """Manually start NGINX container."""
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise HTTPException(status_code=500, detail="Docker CLI not found.")
    try:
        res = subprocess.run([docker_bin, "start", "nginx"], capture_output=True, text=True, timeout=15)
        log_activity(
            event_type="MANUAL_START",
            title="Manual Service Start",
            description="Operator manually started NGINX container.",
            badge_color="blue"
        )
        return {"status": "success", "output": res.stdout.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simulate/trigger-recovery")
def simulate_trigger_recovery():
    """Manually trigger the Ansible playbook to verify execution."""
    res = execute_ansible_playbook()
    return res

def _cpu_stress_worker(duration_seconds: int = 10):
    end_time = time.time() + duration_seconds
    while time.time() < end_time:
        _ = [x * x for x in range(10000)]

@app.post("/api/simulate/cpu-load")
def simulate_cpu_load(background_tasks: BackgroundTasks, duration: int = 15):
    """Safely simulate a CPU spike for the specified duration."""
    threads = []
    thread_count = min(os.cpu_count() or 2, 4)
    for _ in range(thread_count):
        t = threading.Thread(target=_cpu_stress_worker, args=(duration,))
        threads.append(t)
        t.start()

    log_activity(
        event_type="CPU_STRESS",
        title="High CPU Simulation Triggered",
        description=f"Synthetic CPU load initiated for {duration} seconds to verify threshold monitoring.",
        badge_color="orange"
    )
    return {
        "status": "success",
        "message": f"CPU load generation started on {thread_count} threads for {duration} seconds."
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
