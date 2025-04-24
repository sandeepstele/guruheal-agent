import logging.config

import uvicorn

from core.config import settings
from core.log_config import get_log_config
import logfire

logging.config.dictConfig(get_log_config())

logfire.configure(token='zmLFCyY7Pzr852mBPwDC9SRNFlDmxGPsxfZ8NRQNDzpY')

# Keep this so we can run uvicorn main:app --host=0.0.0.0 --port=8000 --reload
from core.server import app

if __name__ == "__main__":
    uvicorn.run(
        app="core.server:app",
        port=settings.APP_PORT,
        reload=True if settings.ENVIRONMENT != "production" else False,
        log_config=get_log_config()
    )
