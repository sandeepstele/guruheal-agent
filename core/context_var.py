import contextvars

correlation_id_ctx_var = contextvars.ContextVar("correlation_id", default=None)
