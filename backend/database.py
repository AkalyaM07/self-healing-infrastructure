import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DB_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "self_healing.db"))

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alertname TEXT NOT NULL,
        status TEXT NOT NULL,
        severity TEXT NOT NULL,
        service TEXT NOT NULL,
        summary TEXT,
        description TEXT,
        starts_at TEXT,
        ends_at TEXT,
        raw_payload TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # Recovery History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recovery_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT UNIQUE NOT NULL,
        service_name TEXT NOT NULL,
        failure_reason TEXT NOT NULL,
        detection_time TEXT NOT NULL,
        recovery_action TEXT NOT NULL,
        recovery_start_time TEXT,
        recovery_result TEXT NOT NULL,
        recovery_completion_time TEXT,
        execution_output TEXT
    )
    """)

    # Activity Timeline Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        badge_color TEXT NOT NULL
    )
    """)

    # Add initial "System Initialized" timeline entry if empty
    cursor.execute("SELECT COUNT(*) FROM activity_timeline")
    if cursor.fetchone()[0] == 0:
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO activity_timeline (timestamp, event_type, title, description, badge_color)
            VALUES (?, ?, ?, ?, ?)
        """, (
            now_iso,
            "SYSTEM_INIT",
            "Self-Healing Monitoring Initialized",
            "Prometheus metrics collector, Alertmanager engine and Ansible auto-recovery agent online.",
            "blue"
        ))

    conn.commit()
    conn.close()

def log_activity(event_type: str, title: str, description: str, badge_color: str = "blue"):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO activity_timeline (timestamp, event_type, title, description, badge_color)
            VALUES (?, ?, ?, ?, ?)
        """, (now_iso, event_type, title, description, badge_color))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] log_activity failed: {e}")

def record_alert(alertname: str, status: str, severity: str, service: str, summary: str, description: str, starts_at: str, ends_at: Optional[str], raw_payload: str = "") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO alerts (alertname, status, severity, service, summary, description, starts_at, ends_at, raw_payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (alertname, status, severity, service, summary, description, starts_at, ends_at, raw_payload, now_iso))
    alert_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return alert_id

def create_recovery_record(event_id: str, service_name: str, failure_reason: str, detection_time: str, recovery_action: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO recovery_history (event_id, service_name, failure_reason, detection_time, recovery_action, recovery_start_time, recovery_result, recovery_completion_time, execution_output)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (event_id, service_name, failure_reason, detection_time, recovery_action, detection_time, "RECOVERY STARTED", None, ""))
    rec_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return rec_id

def update_recovery_record(event_id: str, recovery_result: str, completion_time: str, execution_output: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE recovery_history
        SET recovery_result = ?, recovery_completion_time = ?, execution_output = ?
        WHERE event_id = ?
    """, (recovery_result, completion_time, execution_output, event_id))
    conn.commit()
    conn.close()

def get_recent_recovery_for_service(service_name: str, within_seconds: int = 30) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM recovery_history
        WHERE service_name = ?
        ORDER BY id DESC LIMIT 1
    """, (service_name,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    rec = dict(row)
    # Check start time difference
    try:
        start_dt = datetime.fromisoformat(rec["recovery_start_time"].replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        diff = (now_dt - start_dt).total_seconds()
        if diff < within_seconds:
            return rec
    except Exception:
        pass
    return None

def get_all_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_recovery_history(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM recovery_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_activity(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM activity_timeline ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recovery_statistics() -> Dict[str, int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM recovery_history WHERE recovery_result = 'RECOVERED'")
    successful = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM recovery_history WHERE recovery_result = 'RECOVERY FAILED'")
    failed = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE status = 'firing'")
    firing_alerts = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM alerts")
    total_alerts = cursor.fetchone()[0]
    conn.close()
    return {
        "successful_recoveries": successful,
        "failed_recoveries": failed,
        "firing_alerts": firing_alerts,
        "total_alerts": total_alerts
    }
