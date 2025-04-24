import logging
import os

import uvicorn.config
from .middleware import correlation_id_ctx_var


class CorrelationIdFilter(logging.Filter):
    def filter(self, record):
        correlation_id = correlation_id_ctx_var.get()
        if not correlation_id:
            correlation_id = getattr(record, 'correlation_id', '**')
        record.correlation_id = correlation_id
        return True


# @setup_logging.connect
def get_log_config(*args, **kwargs):
    # Get base config from uvicorn
    log_config = uvicorn.config.LOGGING_CONFIG

    # Initialize filters dictionary if it doesn't exist
    if "filters" not in log_config:
        log_config["filters"] = {}

    # Add correlation ID filter
    log_config["filters"]['correlation_id'] = {
        "()": CorrelationIdFilter
    }

    # Update formatters to include correlation ID
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s- [ %(correlation_id)s ] - %(message)s"
    log_config["formatters"]["access"][
        "fmt"] = '%(asctime)s %(levelprefix)s- [ %(correlation_id)s ]- %(client_addr)s - "%(request_line)s" %(status_code)s'

    # Configure root logger
    log_config["loggers"][""] = {  # Empty string represents root logger
        "handlers": ["default"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
        "propagate": False
    }

    # Add filter to all handlers
    for handler in log_config["handlers"].values():
        if "filters" not in handler:
            handler["filters"] = []
        if "correlation_id" not in handler["filters"]:
            handler["filters"].append('correlation_id')

    return log_config
