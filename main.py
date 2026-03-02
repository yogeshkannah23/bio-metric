"""
Entry point — run with:  python main.py
"""

import uvicorn
import config
from app import app

if __name__ == '__main__':
    uvicorn.run(
        app,
        host=config.ADMS_SERVER_HOST,
        port=config.ADMS_SERVER_PORT,
        log_level="warning",
        access_log=False,
    )
