"""
Configuration — loads from local_config.py and exposes all constants.
"""

try:
    import local_config as _cfg
except ImportError:
    print("ERROR: local_config.py not found.")
    exit(1)

ADMS_SERVER_HOST = getattr(_cfg, 'ADMS_SERVER_HOST', '0.0.0.0')
ADMS_SERVER_PORT = getattr(_cfg, 'ADMS_SERVER_PORT', 8090)
LOGS_DIRECTORY   = getattr(_cfg, 'LOGS_DIRECTORY',   'logs')
PUSH_TO_ERP      = getattr(_cfg, 'PUSH_TO_ERP',      False)
ERPNEXT_VERSION  = getattr(_cfg, 'ERPNEXT_VERSION',  14)

ERPNEXT_URL        = _cfg.ERPNEXT_URL
ERPNEXT_API_KEY    = _cfg.ERPNEXT_API_KEY
ERPNEXT_API_SECRET = _cfg.ERPNEXT_API_SECRET
devices            = _cfg.devices

EMPLOYEE_NOT_FOUND_ERROR  = "No Employee found for the given employee field value"
EMPLOYEE_INACTIVE_ERROR   = "Transactions cannot be created for an Inactive Employee"
DUPLICATE_CHECKIN_ERROR   = "This employee already has a log with the same timestamp"
ALLOWLISTED_ERRORS = [EMPLOYEE_NOT_FOUND_ERROR, EMPLOYEE_INACTIVE_ERROR, DUPLICATE_CHECKIN_ERROR]

EMPLOYEE_ID_MAP = {
    '21':'SS0021', '24':'SS0024', '01':'SS0001', '14':'SS0014',
    '12':'SS0012', '393':'SS00393', '656':'SS00656', '191':'SS00191',
    '300':'SS00300', '299':'SS00299', '106':'SS00106', '241':'SS00241',
    '493':'SS00493', '707':'SS00707', '664':'SS00664', '306':'SS00306',
    '720':'SS00720', '721':'SS00721', '490':'SS00490', '484':'SS00484',
    '375':'SS00375', '195':'SS00195', '751':'SS00751', '756':'SS00756',
}
