"""
FastAPI application — lifespan startup and all ADMS device endpoints.
"""
# REALTIME_FROM = '2026-03-03 17:00:00'  # Only process checkins at or after this datetime (format: 'YYYY-MM-DD HH:MM:SS')

import json
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse

import config
from logger import info_logger, checkin_logger
from erpnext import send_to_erpnext_or_queue
from adms import (
    get_device_config,
    map_employee_id,
    parse_attendance_line,
)

# =============================================================================
# Lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 64)
    print("  ESSL ADMS Push Server → ERPNext")
    print("=" * 64)
    print()
    print("  Registered devices:")
    for d in config.devices:
        print(f"    {d['device_id']} | {d['ip']} | {d['punch_direction']} | SN: {d.get('serial_number','N/A')}")
    print()
    erp_status = "✓ ENABLED" if config.PUSH_TO_ERP else "✗ DISABLED"
    print(f"  Server:  http://{config.ADMS_SERVER_HOST}:{config.ADMS_SERVER_PORT}")
    print(f"  ERPNext: {erp_status} ({config.ERPNEXT_URL})")
    print()
    print("  Waiting for device data... (keep this running until all records arrive)")
    print("  Press Ctrl+C to stop.")
    print("=" * 64)
    print()

    info_logger.info(f"ADMS server started on {config.ADMS_SERVER_HOST}:{config.ADMS_SERVER_PORT} | Accepting checkins from {config.REALTIME_FROM}")

    yield

    print("\nServer shutting down...")
    info_logger.info("ADMS server stopped")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="ESSL ADMS Push Server",
    description="ADMS data query on startup + live checkin → Log + ERPNext",
    version="7.0.0",
    lifespan=lifespan,
)

# =============================================================================
# Routes
# =============================================================================

@app.get("/", response_class=PlainTextResponse)
async def index():
    return "ADMS Server Running"


@app.api_route("/iclock/cdata",      methods=["GET", "POST"], response_class=PlainTextResponse)
@app.api_route("/iclock/cdata.aspx", methods=["GET", "POST"], response_class=PlainTextResponse)
async def iclock_cdata(
    request: Request,
    SN:    str = Query(default="UNKNOWN"),
    table: str = Query(default="")
):
    """
    Handles real-time checkins only. Records older than the server start
    time are treated as historical device replays and silently skipped.
    """
    if request.method == "GET":
        info_logger.info(f"Handshake SN:{SN}")
        return "OK"

    body = await request.body()
    raw  = body.decode('utf-8', errors='ignore')

    if table != "ATTLOG" or not raw.strip():
        return "OK"

    device_cfg = get_device_config(SN)
    if device_cfg:
        device_id       = device_cfg['device_id']
        punch_direction = device_cfg['punch_direction']
    else:
        device_id       = SN
        punch_direction = 'AUTO'

    seen = set()
    processed = duplicates = 0

    for line in raw.strip().split('\n'):
        if not line.strip():
            continue
        attendance = parse_attendance_line(line)
        if not attendance:
            continue

        if punch_direction in ('IN', 'OUT'):
            log_type = punch_direction
        else:
            log_type = 'OUT' if attendance['punch_status'] in [1, 5] else 'IN'

        employee_id = map_employee_id(attendance['user_id'])

        # Skip historical replays — only accept punches at or after REALTIME_FROM
        if attendance['timestamp'] < config.REALTIME_FROM:
            duplicates += 1
            continue

        key = (employee_id, attendance['timestamp_str'])
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        processed += 1

        checkin_logger.info(json.dumps({
            'employee_id':   employee_id,
            'timestamp':     attendance['timestamp_str'],
            'log_type':      log_type,
            'device_id':     device_id,
            'device_serial': SN,
            'punch_status':  attendance['punch_status'],
        }))

        erp_tag = ""
        if config.PUSH_TO_ERP:
            erp_tag = send_to_erpnext_or_queue(employee_id, attendance['timestamp'], device_id, log_type)
            time.sleep(config.ERP_CALL_DELAY)

        direction_icon = "🟢 IN " if log_type == 'IN' else "🔴 OUT"
        print(f"  {direction_icon} | {employee_id} | {attendance['timestamp_str']} | Dev {device_id}{erp_tag}")

    if processed > 0 or duplicates > 0:
        info_logger.info(f"SN:{SN} | Received:{processed} | Dup:{duplicates}")

    return "OK"


@app.api_route("/iclock/getrequest",      methods=["GET", "POST"], response_class=PlainTextResponse)
@app.api_route("/iclock/getrequest.aspx", methods=["GET", "POST"], response_class=PlainTextResponse)
async def iclock_getrequest(SN: str = Query(default="UNKNOWN")):
    return "OK"


@app.api_route("/iclock/devicecmd",      methods=["GET", "POST"], response_class=PlainTextResponse)
@app.api_route("/iclock/devicecmd.aspx", methods=["GET", "POST"], response_class=PlainTextResponse)
async def iclock_devicecmd(SN: str = Query(default="UNKNOWN")):
    return "OK"


@app.api_route("/iclock/ping",      methods=["GET", "POST"], response_class=PlainTextResponse)
@app.api_route("/iclock/ping.aspx", methods=["GET", "POST"], response_class=PlainTextResponse)
async def iclock_ping():
    return "OK"
