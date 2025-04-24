from __future__ import annotations as _annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.exceptions import HTTPException

# from .faststream import init_fastream_router
from app.api import router
from app.utils.pg_utils import PgDatabase
from .config import settings
from .exception_handler import exception_exception_handler
from .middleware import CorrelationIdMiddleware, LoggingMiddleware
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app_: FastAPI):
    async with PgDatabase.connectToDb() as db:
        yield {'db': db}


def add_middlewares(app_: FastAPI) -> None:
    app_.add_middleware(LoggingMiddleware)
    app_.add_middleware(CorrelationIdMiddleware)
    app_.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Adjust this to your needs
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

def create_app() -> FastAPI:
    app_ = FastAPI(
        title=settings.APP_NAME,
        description=settings.APP_DESCRIPTION,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
        redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    )

    # Add Exception handler
    app_.add_exception_handler(Exception, exception_exception_handler)
    app_.add_exception_handler(HTTPException, exception_exception_handler)

    # app_.add_middleware(LoggingMiddleware)
    # app_.add_middleware(CorrelationIdMiddleware)
    add_middlewares(app_)
    # init_routers(app_=app_)

    app_.include_router(router)

    return app_


app = create_app()
Instrumentator().instrument(app).expose(app)
