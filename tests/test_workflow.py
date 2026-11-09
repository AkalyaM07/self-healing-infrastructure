import sys
import os
import unittest
from datetime import datetime, timezone

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from fastapi.testclient import TestClient
from main import app
from database import init_db, get_db_connection

class TestSelfHealingInfrastructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize test database
        os.environ["DATABASE_PATH"] = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "database", "test_self_healing.db"))
        init_db()
        cls.client = TestClient(app)

    def test_01_health_check(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["playbook_available"])
        print("PASS: test_01_health_check")

    def test_02_server_status(self):
        resp = self.client.get("/api/server-status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("infrastructure_status", data)
        self.assertIn("cpu_percent", data)
        self.assertIn("memory_percent", data)
        self.assertIn("disk_percent", data)
        self.assertIn("successful_recoveries", data)
        print("PASS: test_02_server_status")

    def test_03_metrics(self):
        resp = self.client.get("/api/metrics")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("current_cpu", data)
        self.assertIn("current_memory", data)
        self.assertIn("history_timestamps", data)
        self.assertIn("history_cpu", data)
        print("PASS: test_03_metrics")

    def test_04_high_cpu_alert_notification_only(self):
        """HighCPUUsage should record alert and notify, but NOT trigger NGINX restart."""
        payload = {
            "version": "4",
            "status": "firing",
            "receiver": "fastapi-webhook",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPUUsage",
                        "severity": "warning",
                        "service": "system",
                        "action": "notify_only"
                    },
                    "annotations": {
                        "summary": "Host CPU utilization is critically high (>90%)",
                        "description": "CPU usage on node-exporter has exceeded 90% for 30s."
                    },
                    "startsAt": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        resp = self.client.post("/webhook/alerts", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["processed_count"], 1)
        self.assertEqual(data["results"][0]["action"], "NOTIFIED")
        print("PASS: test_04_high_cpu_alert_notification_only")

    def test_05_nginx_down_alert_triggers_recovery(self):
        """NGINXDown alert must trigger recovery pipeline, record in DB, and create timeline event."""
        payload = {
            "version": "4",
            "status": "firing",
            "receiver": "fastapi-webhook",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "NGINXDown",
                        "severity": "critical",
                        "service": "nginx",
                        "action": "auto_recover"
                    },
                    "annotations": {
                        "summary": "NGINX service is down",
                        "description": "Blackbox prober failed to reach NGINX web server at http://nginx:80."
                    },
                    "startsAt": datetime.now(timezone.utc).isoformat()
                }
            ]
        }
        resp = self.client.post("/webhook/alerts", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["processed_count"], 1)
        self.assertIn("event_id", data["results"][0])
        self.assertIn(data["results"][0]["action"], ["RECOVERED", "RECOVERY FAILED"])
        print(f"PASS: test_05_nginx_down_alert_triggers_recovery (Event: {data['results'][0]['event_id']}, Action: {data['results'][0]['action']})")

    def test_06_recovery_history_endpoint(self):
        resp = self.client.get("/api/recovery-history")
        self.assertEqual(resp.status_code, 200)
        history = resp.json()
        self.assertIsInstance(history, list)
        self.assertGreaterEqual(len(history), 1)
        first_event = history[0]
        self.assertEqual(first_event["service_name"], "nginx")
        self.assertIn("restart_nginx.yml", first_event["recovery_action"])
        print("PASS: test_06_recovery_history_endpoint")

    def test_07_activity_timeline_endpoint(self):
        resp = self.client.get("/api/activity")
        self.assertEqual(resp.status_code, 200)
        activity = resp.json()
        self.assertIsInstance(activity, list)
        self.assertGreaterEqual(len(activity), 1)
        print("PASS: test_07_activity_timeline_endpoint")

    def test_08_debouncing_duplicate_recovery(self):
        """Simulate rapid duplicate alert while recovery is underway."""
        # Insert a fresh RECOVERY STARTED entry in DB
        from database import create_recovery_record
        import uuid
        event_id = f"REC-DEBOUNCE-{uuid.uuid4().hex[:6].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        create_recovery_record(event_id, "nginx", "Synthetic probe failure", now_iso, "Ansible Playbook")

        payload = {
            "version": "4",
            "status": "firing",
            "receiver": "fastapi-webhook",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "NGINXDown",
                        "severity": "critical",
                        "service": "nginx"
                    },
                    "annotations": {
                        "summary": "NGINX service is down",
                        "description": "Blackbox probe failed."
                    },
                    "startsAt": now_iso
                }
            ]
        }
        resp = self.client.post("/webhook/alerts", json=payload)
        data = resp.json()
        self.assertEqual(data["results"][0]["action"], "DEBOUNCED")
        print("PASS: test_08_debouncing_duplicate_recovery")

    def test_09_frontend_served(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("SELF-HEALING INFRASTRUCTURE", resp.text)
        print("PASS: test_09_frontend_served")

if __name__ == "__main__":
    unittest.main()
