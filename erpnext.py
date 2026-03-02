"""
ERPNext — push employee checkins via the HRMS API.
Includes a persistent SQLite retry queue for failed pushes.
"""

import json
import os
import sqlite3
import threading
import time

import requests as http_requests

import config
from logger import error_logger, info_logger

# =============================================================================
# Retry queue (SQLite)
# =============================================================================

_DB_PATH = os.path.join(config.LOGS_DIRECTORY, 'retry_queue.db')
_lock = threading.Lock()


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the retry table if it does not already exist."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS failed_checkins (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL,
                device_id   TEXT,
                log_type    TEXT,
                attempts    INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
        """)


def _enqueue(employee_id, timestamp, device_id, log_type):
    """Store a failed checkin for later retry."""
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO failed_checkins (employee_id, timestamp, device_id, log_type)"
            " VALUES (?, ?, ?, ?)",
            (str(employee_id), str(timestamp), device_id, log_type),
        )


def _remove(record_id):
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM failed_checkins WHERE id = ?", (record_id,))


def _increment(record_id):
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE failed_checkins SET attempts = attempts + 1 WHERE id = ?",
            (record_id,),
        )


def retry_pending():
    """
    Called once on server startup.
    Replays every record that previously failed to reach ERPNext.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM failed_checkins ORDER BY created_at"
        ).fetchall()

    if not rows:
        return

    print(f"  Retrying {len(rows)} queued ERP record(s)...")
    ok = skipped = still_failing = 0

    for row in rows:
        code, msg = send_to_erpnext(
            row['employee_id'], row['timestamp'],
            row['device_id'],   row['log_type'],
        )
        if code == 200:
            _remove(row['id'])
            ok += 1
            print(f"    ✓ {row['employee_id']} @ {row['timestamp']}")
        elif any(err in str(msg) for err in config.ALLOWLISTED_ERRORS):
            _remove(row['id'])
            skipped += 1
            print(f"    ~ {row['employee_id']} @ {row['timestamp']} (skipped)")
        else:
            _increment(row['id'])
            still_failing += 1
            print(f"    ✗ {row['employee_id']} @ {row['timestamp']} ({code})")
        time.sleep(0.3)

    info_logger.info(
        f"Retry run: {ok} pushed, {skipped} skipped, {still_failing} still failing"
    )
    print()


# =============================================================================
# ERPNext push
# =============================================================================

def _safe_get_error_str(res) -> str:
    try:
        err = json.loads(res._content)
        if 'exc' in err:
            return json.loads(err['exc'])[0]
        return json.dumps(err)
    except Exception:
        return str(res.__dict__)


def send_to_erpnext(employee_field_value, timestamp, device_id=None, log_type=None):
    """Push one checkin to ERPNext. Returns (status_code, name_or_error)."""
    employee_field_value = config.EMPLOYEE_ID_MAP.get(
        str(employee_field_value), str(employee_field_value)
    )

    endpoint_app = "hrms" if config.ERPNEXT_VERSION > 13 else "erpnext"
    url = (
        f"{config.ERPNEXT_URL}/api/method/"
        f"{endpoint_app}.hr.doctype.employee_checkin.employee_checkin"
        f".add_log_based_on_employee_field"
    )
    headers = {
        'Authorization': "token " + config.ERPNEXT_API_KEY + ":" + config.ERPNEXT_API_SECRET,
        'Accept': 'application/json',
    }
    data = {
        'employee_field_value': employee_field_value,
        'timestamp': str(timestamp),
        'device_id': device_id,
        'log_type': log_type,
    }
    try:
        response = http_requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return 200, json.loads(response._content)['message']['name']
        error_str = _safe_get_error_str(response)
        error_logger.error('\t'.join([
            'ERP Error', str(employee_field_value),
            str(timestamp), str(device_id), str(log_type), error_str
        ]))
        return response.status_code, error_str
    except Exception as e:
        error_logger.error(f"ERPNext connection error for {employee_field_value}: {e}")
        return 0, str(e)


def send_to_erpnext_or_queue(employee_id, timestamp, device_id, log_type):
    """
    Push one checkin. On failure (non-allowlisted), persist to the retry queue.
    Returns a display tag string.
    """
    code, msg = send_to_erpnext(employee_id, timestamp, device_id, log_type)
    if code == 200:
        return " → ERP ✓"
    if any(err in str(msg) for err in config.ALLOWLISTED_ERRORS):
        return " → ERP (skipped)"
    # Transient failure — store for retry on next startup
    _enqueue(employee_id, timestamp, device_id, log_type)
    return f" → ERP ✗ ({code}) [queued]"
