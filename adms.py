"""
ADMS — device configuration lookup and attendance line parsing.
"""

import datetime

import config
from logger import error_logger


def get_device_config(serial_number):
    for d in config.devices:
        if d.get('serial_number') == serial_number:
            return d
    return None


def map_employee_id(user_id):
    return config.EMPLOYEE_ID_MAP.get(str(user_id), str(user_id))


def parse_attendance_line(line):
    parts = line.strip().split('\t')
    if len(parts) < 3:
        return None
    try:
        user_id       = parts[0].strip()
        timestamp_str = parts[1].strip()
        punch_status  = int(parts[2].strip()) if len(parts) > 2 else 0
        timestamp     = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return {
            'user_id':       user_id,
            'timestamp':     timestamp,
            'timestamp_str': timestamp_str,
            'punch_status':  punch_status,
        }
    except (ValueError, IndexError) as e:
        error_logger.error(f"Parse error: {line} — {e}")
        return None
