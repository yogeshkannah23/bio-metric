# ESSL ADMS Push Server → ERPNext

A lightweight FastAPI server that receives attendance push data from **ESSL/ZKTeco ADMS biometric devices** and forwards it to **ERPNext HRMS** as Employee Check-in records. Failed pushes are persisted in a local SQLite retry queue and replayed automatically on the next startup.

---

## How it works

```
Biometric Device  →  POST /iclock/cdata  →  FastAPI Server  →  ERPNext HRMS API
                                                    ↓ (on failure)
                                             SQLite retry queue
                                                    ↓ (on next startup)
                                             ERPNext HRMS API
```

1. The biometric device is configured to push attendance logs to this server.
2. The server parses each `ATTLOG` record (employee ID, timestamp, punch status).
3. Each record is mapped to an ERPNext employee ID and sent via the HRMS checkin API.
4. If the push fails with a transient error, the record is stored in a SQLite queue and retried on the next server startup.
5. Every checkin is also written to rotating log files for audit purposes.

---

## Project structure

```
bio-metric/
├── main.py            # Entry point — starts the uvicorn server
├── app.py             # FastAPI app and ADMS device endpoints
├── adms.py            # Device config lookup and attendance line parser
├── erpnext.py         # ERPNext API push + SQLite retry queue
├── config.py          # Configuration loader (reads local_config.py)
├── logger.py          # Three rotating file loggers
├── requirements.txt   # Python dependencies
├── local_config.py    # (create this — see Configuration below)
└── logs/              # Created automatically at runtime
    ├── adms_logs.log
    ├── adms_checkin.log
    ├── adms_error.log
    └── retry_queue.db
```

---

## Requirements

- Python 3.9+
- ERPNext v13 or v14 with HRMS installed

---

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd bio-metric

# Install dependencies
pip install -r requirements.txt

# Create your local configuration (see below)
cp local_config.py.example local_config.py   # or create from scratch
```

---

## Configuration

Create `local_config.py` in the project root. **Do not commit this file** — it contains credentials.

```python
# ERPNext connection
ERPNEXT_URL        = 'http://your-erpnext-instance'
ERPNEXT_API_KEY    = 'your_api_key'
ERPNEXT_API_SECRET = 'your_api_secret'
ERPNEXT_VERSION    = 14          # 13 or 14

# Push behaviour
PUSH_TO_ERP        = True        # Set to False to log only (no ERP push)
LOGS_DIRECTORY     = 'logs'

# ADMS push server
ADMS_SERVER_HOST   = '0.0.0.0'  # Bind to all interfaces
ADMS_SERVER_PORT   = 8090

# Registered biometric devices
devices = [
    {
        'device_id':                 '1',             # Unique alphanumeric ID (no spaces)
        'ip':                        '192.168.1.100',
        'punch_direction':           'IN',            # 'IN', 'OUT', or 'AUTO'
        'clear_from_device_on_fetch': False,
        'port':                      4370,
        'serial_number':             'DEVICE_SERIAL',
        'password':                  123456,
    },
]
```

### `punch_direction` values

| Value  | Behaviour |
|--------|-----------|
| `IN`   | All punches from this device are treated as Check-In |
| `OUT`  | All punches from this device are treated as Check-Out |
| `AUTO` | Direction is inferred from the device's punch status code |

---

## Running the server

```bash
python main.py
```

The server starts on `http://0.0.0.0:8090` (or whatever port you configured).

Point your biometric device's **ADMS server address** to this machine's IP and port.

---

## Biometric device setup

In the device's network / cloud server settings:

| Field           | Value                          |
|-----------------|-------------------------------|
| Server address  | `<this-machine-ip>`            |
| Port            | `8090` (or your configured port) |
| Protocol        | HTTP / ADMS push               |

---

## API endpoints

| Method | Path                        | Description                          |
|--------|-----------------------------|--------------------------------------|
| GET    | `/`                         | Health check                         |
| GET/POST | `/iclock/cdata`           | Handshake + attendance data receiver |
| GET/POST | `/iclock/cdata.aspx`     | Alias (some firmware variants)       |
| GET/POST | `/iclock/getrequest`     | Device command poll (returns OK)     |
| GET/POST | `/iclock/devicecmd`      | Device command ack (returns OK)      |
| GET/POST | `/iclock/ping`           | Keepalive ping (returns OK)          |

---

## Logs

All logs are written to the `logs/` directory with 10 MB rotation (10 backups kept):

| File               | Contents                                      |
|--------------------|-----------------------------------------------|
| `adms_logs.log`    | Server start/stop, record counts, retry runs  |
| `adms_checkin.log` | One JSON line per checkin received             |
| `adms_error.log`   | Parse errors and ERPNext API errors            |
| `retry_queue.db`   | SQLite database of failed ERP pushes           |

---

## Retry queue

When an ERPNext push fails with a transient error (network issue, server down), the record is saved to `logs/retry_queue.db`. On the **next server startup**, all queued records are replayed automatically.

Records are silently discarded (not retried) if ERPNext returns one of these known-safe errors:

- Employee not found for the given ID
- Employee is inactive
- Duplicate checkin timestamp

---

## Employee ID mapping

The `EMPLOYEE_ID_MAP` dict in `config.py` maps raw device user IDs to ERPNext employee IDs. Extend it as needed:

```python
EMPLOYEE_ID_MAP = {
    '1': 'EMP-001',
    '2': 'EMP-002',
}
```

If a device user ID is not in the map, it is passed through to ERPNext as-is.
