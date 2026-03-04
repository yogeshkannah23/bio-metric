"""
Plain Python HTTP server — ESSL ADMS Push Server → ERPNext.
No FastAPI/uvicorn required. Uses only stdlib + requests.

Run with:  python server.py
"""

import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import config
from logger import info_logger, checkin_logger
from erpnext import send_to_erpnext_or_queue
from adms import get_device_config, map_employee_id, parse_attendance_line


class ADMSHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Suppress default HTTP access log output
        pass

    def _send_ok(self, body="OK"):
        encoded = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _path(self):
        return urlparse(self.path).path

    def _params(self):
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    # ------------------------------------------------------------------
    # GET
    # ------------------------------------------------------------------

    def do_GET(self):
        path   = self._path()
        params = self._params()

        if path == '/':
            self._send_ok("ADMS Server Running")
            return

        if path in ('/iclock/cdata', '/iclock/cdata.aspx'):
            SN = params.get('SN', 'UNKNOWN')
            info_logger.info(f"Handshake SN:{SN}")
            self._send_ok("OK")
            return

        # getrequest / devicecmd / ping — just ack
        self._send_ok("OK")

    # ------------------------------------------------------------------
    # POST
    # ------------------------------------------------------------------

    def do_POST(self):
        path   = self._path()
        params = self._params()

        if path in ('/iclock/cdata', '/iclock/cdata.aspx'):
            self._handle_attlog(params)
            return

        # All other POST routes
        self._send_ok("OK")

    # ------------------------------------------------------------------
    # Attendance log handler
    # ------------------------------------------------------------------

    def _handle_attlog(self, params):
        SN    = params.get('SN',    'UNKNOWN')
        table = params.get('table', '')

        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length).decode('utf-8', errors='ignore') if length else ''

        if table != 'ATTLOG' or not raw.strip():
            self._send_ok("OK")
            return

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

        self._send_ok("OK")


# =============================================================================
# Entry point
# =============================================================================

def main():
    print("=" * 64)
    print("  ESSL ADMS Push Server → ERPNext")
    print("=" * 64)
    print()
    print("  Registered devices:")
    for d in config.devices:
        print(f"    {d['device_id']} | {d['ip']} | {d['punch_direction']} | SN: {d.get('serial_number', 'N/A')}")
    print()
    erp_status = "✓ ENABLED" if config.PUSH_TO_ERP else "✗ DISABLED"
    print(f"  Server:  http://{config.ADMS_SERVER_HOST}:{config.ADMS_SERVER_PORT}")
    print(f"  ERPNext: {erp_status} ({config.ERPNEXT_URL})")
    print()
    print("  Waiting for device data... (keep this running until all records arrive)")
    print("  Press Ctrl+C to stop.")
    print("=" * 64)
    print()

    info_logger.info(
        f"ADMS server started on {config.ADMS_SERVER_HOST}:{config.ADMS_SERVER_PORT}"
        f" | Accepting checkins from {config.REALTIME_FROM}"
    )

    server = HTTPServer((config.ADMS_SERVER_HOST, config.ADMS_SERVER_PORT), ADMSHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        info_logger.info("ADMS server stopped")
        server.server_close()


if __name__ == '__main__':
    main()
