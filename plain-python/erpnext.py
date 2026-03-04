"""
ERPNext — push employee checkins via the HRMS API.
"""

import json

import requests as http_requests

import config
from logger import error_logger


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
    """Push one checkin. Returns a display tag string."""
    code, msg = send_to_erpnext(employee_id, timestamp, device_id, log_type)
    if code == 200:
        return " → ERP ✓"
    if any(err in str(msg) for err in config.ALLOWLISTED_ERRORS):
        return " → ERP (skipped)"
    return f" → ERP ✗ ({code})"
