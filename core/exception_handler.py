import logging
import traceback
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .middleware import correlation_id_ctx_var


def _get_error_json_response(request: Request, error_content: Any, status_code=500, ) -> JSONResponse:
    correlation_id = request.headers.get("x-correlation-id")
    if not correlation_id:
        correlation_id = correlation_id_ctx_var.get() or str(uuid.uuid4())

    return JSONResponse(status_code=status_code,
                        headers={"x-correlation-id": correlation_id},
                        content={
                            "error": error_content,
                            "correlation_id": correlation_id
                        })


async def exception_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return _get_error_json_response(request, exc.detail, exc.status_code)
    logging.error(traceback.format_exc())
    return _get_error_json_response(request, str(exc))
