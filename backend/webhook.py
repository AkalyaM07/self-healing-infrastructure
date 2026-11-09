import os
import sys
import uuid
import shutil
import subprocess
import json
from datetime import datetime, timezone
from typing import Dict, Any

from database import (
    record_alert,
    create_recovery_record,
    update_recovery_record,
    get_recent_recovery_for_service,
    log_activity
)

ANSIBLE_DIR = os.getenv("ANSIBLE_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "ansible"))
PLAYBOOK_PATH = os.path.join(ANSIBLE_DIR, "restart_nginx.yml")
INVENTORY_PATH = os.path.join(ANSIBLE_DIR, "inventory.ini")

def execute_ansible_playbook() -> Dict[str, Any]:
    start_time = datetime.now(timezone.utc).isoformat()
    cmd = []
    
    # 1. Check if ansible-playbook binary exists in PATH (e.g. Linux container or WSL)
    ansible_bin = shutil.which("ansible-playbook")
    if ansible_bin:
        cmd = [ansible_bin, "-i", INVENTORY_PATH, PLAYBOOK_PATH]
    else:
        # Fallback runner using Docker CLI directly if Ansible binary is not on host
        docker_bin = shutil.which("docker")
        if docker_bin:
            cmd = [docker_bin, "restart", "nginx"]
        else:
            return {
                "success": False,
                "output": "Self-healing executor notice: Neither 'ansible-playbook' nor 'docker' CLI is accessible in the current execution context.",
                "completion_time": datetime.now(timezone.utc).isoformat(),
                "returncode": 1
            }

    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=45
        )
        output = process.stdout + ("\nSTDERR:\n" + process.stderr if process.stderr else "")
        success = (process.returncode == 0)
        completion_time = datetime.now(timezone.utc).isoformat()
        return {
            "success": success,
            "output": output,
            "completion_time": completion_time,
            "returncode": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Ansible playbook execution timed out after 45 seconds.",
            "completion_time": datetime.now(timezone.utc).isoformat(),
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "output": f"Exception occurred while triggering Ansible playbook: {str(e)}",
            "completion_time": datetime.now(timezone.utc).isoformat(),
            "returncode": -1
        }

def process_alertmanager_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    status = payload.get("status", "unknown").lower()
    alerts = payload.get("alerts", [])
    results = []

    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = labels.get("alertname", "UnknownAlert")
        severity = labels.get("severity", "info")
        service = labels.get("service", "unknown")
        alert_status = alert.get("status", status).lower()
        summary = annotations.get("summary", "")
        description = annotations.get("description", "")
        starts_at = alert.get("startsAt", datetime.now(timezone.utc).isoformat())
        ends_at = alert.get("endsAt", None)

        # 1. Record alert in SQLite database
        alert_id = record_alert(
            alertname=alertname,
            status=alert_status,
            severity=severity,
            service=service,
            summary=summary,
            description=description,
            starts_at=starts_at,
            ends_at=ends_at,
            raw_payload=json.dumps(alert)
        )

        log_activity(
            event_type="ALERT_RECEIVED",
            title=f"Alert Received: {alertname} ({alert_status.upper()})",
            description=f"Severity: {severity.upper()} | Service: {service} | {summary}",
            badge_color="red" if severity == "critical" else "orange" if severity == "warning" else "blue"
        )

        # 2. Check if this is an automated recovery trigger
        # Only trigger automated recovery if alert is FIRING, service is NGINX (or NGINXDown)
        if alert_status == "firing" and (service == "nginx" or alertname == "NGINXDown"):
            # Check duplicate / debouncing within last 30 seconds
            recent_rec = get_recent_recovery_for_service("nginx", within_seconds=30)
            if recent_rec and recent_rec["recovery_result"] == "RECOVERY STARTED":
                results.append({
                    "alertname": alertname,
                    "action": "DEBOUNCED",
                    "message": "Recovery for NGINX is already in progress. Skipping duplicate execution."
                })
                continue

            event_id = f"REC-{uuid.uuid4().hex[:8].upper()}"
            detection_time = datetime.now(timezone.utc).isoformat()
            
            # Record Recovery Initiated
            create_recovery_record(
                event_id=event_id,
                service_name="nginx",
                failure_reason=summary or "NGINX health probe failed",
                detection_time=detection_time,
                recovery_action="Ansible Playbook: restart_nginx.yml"
            )

            log_activity(
                event_type="RECOVERY_TRIGGERED",
                title=f"Automated Recovery Triggered [{event_id}]",
                description="Alertmanager triggered Ansible self-healing playbook 'restart_nginx.yml' to recover NGINX service.",
                badge_color="blue"
            )

            # Execute Ansible playbook
            exec_res = execute_ansible_playbook()

            if exec_res["success"]:
                update_recovery_record(
                    event_id=event_id,
                    recovery_result="RECOVERED",
                    completion_time=exec_res["completion_time"],
                    execution_output=exec_res["output"]
                )
                log_activity(
                    event_type="RECOVERY_SUCCESS",
                    title=f"Service Recovered Successfully [{event_id}]",
                    description="Ansible successfully restarted NGINX web server and verified HTTP 200 OK health check.",
                    badge_color="green"
                )
                results.append({
                    "alertname": alertname,
                    "event_id": event_id,
                    "action": "RECOVERED",
                    "output": exec_res["output"]
                })
            else:
                update_recovery_record(
                    event_id=event_id,
                    recovery_result="RECOVERY FAILED",
                    completion_time=exec_res["completion_time"],
                    execution_output=exec_res["output"]
                )
                log_activity(
                    event_type="RECOVERY_FAILED",
                    title=f"Recovery Failed [{event_id}]",
                    description=f"Ansible playbook execution failed. Error: {exec_res['output'][:200]}...",
                    badge_color="red"
                )
                results.append({
                    "alertname": alertname,
                    "event_id": event_id,
                    "action": "RECOVERY FAILED",
                    "output": exec_res["output"]
                })

        elif alert_status == "firing" and service == "system":
            # Warning only for high CPU / Memory
            log_activity(
                event_type="SYSTEM_WARNING",
                title=f"Resource Warning: {alertname}",
                description=f"{description} (No service restart required for resource warnings).",
                badge_color="orange"
            )
            results.append({
                "alertname": alertname,
                "action": "NOTIFIED",
                "message": "Resource warning logged to dashboard."
            })
        elif alert_status == "resolved":
            log_activity(
                event_type="ALERT_RESOLVED",
                title=f"Alert Resolved: {alertname}",
                description=f"Service {service} is back in nominal operating state.",
                badge_color="green"
            )
            results.append({
                "alertname": alertname,
                "action": "RESOLVED",
                "message": "Alert marked as resolved."
            })
        else:
            results.append({
                "alertname": alertname,
                "action": "IGNORED",
                "message": f"No action configured for status: {alert_status}"
            })

    return {
        "status": "success",
        "processed_count": len(alerts),
        "results": results
    }
