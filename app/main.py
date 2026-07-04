from contextlib import asynccontextmanager
import time
import uuid
import structlog
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from typing import Callable, Any, Coroutine
import pickle

from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
)

from .core.config import settings
from .core.logging import setup_logging
from .routers import health, language
from .core.exceptions import LanguagePredictionError
from .core.handlers import (
    validation_exception_handler,
    language_prediction_error_handler,
)


ExceptionHandler = Callable[[Request, Any], Coroutine[Any, Any, Response]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, settings.log_format)
    log = structlog.get_logger()

    # Load the model once at startup, before the app accepts requests,
    # so every request reuses the same in-memory object.
    log.info("startup")
    log.info("model_loading", path=settings.model_path)

    try:
        with open(settings.model_path, "rb") as file:
            app.state.model = pickle.load(file)
        log.info("model_loaded", path=settings.model_path)
    except FileNotFoundError:
        # Leave the model unset so the dependency detects it and the
        # service raises ModelUnavailableError (503).
        log.error(
            "model_load_failed", path=settings.model_path, reason="file_not_found"
        )
        app.state.model = None
    except Exception:
        # log.exception captures the full traceback as structured data.
        log.exception("model_load_failed", path=settings.model_path)
        app.state.model = None
    yield
    log.info("shutdown")
    app.state.model = None


def create_app(
    routers: list[APIRouter],
    exception_handlers: dict[int | type[Exception], ExceptionHandler],
) -> FastAPI:
    """
    Factory for creating the app with everything it needs.

    Accepts a list of routers and a mapping of exception types to their
    handlers, so both are wired in declaratively instead of scattering
    include_router and add_exception_handler calls. Returns the full app.
    """
    app = FastAPI(lifespan=lifespan, exception_handlers=exception_handlers)
    for router in routers:
        app.include_router(router)

    return app


routers = [health.router, language.router]

exception_handlers: dict[int | type[Exception], ExceptionHandler] = {
    RequestValidationError: validation_exception_handler,
    LanguagePredictionError: language_prediction_error_handler,
}

app = create_app(routers, exception_handlers)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    log = structlog.get_logger()

    request_id = str(uuid.uuid4())
    bind_contextvars(request_id=request_id)
    start_time = time.perf_counter()

    log.debug("request_started", method=request.method, path=request.url.path)

    try:
        response = await call_next(request)
    except Exception:
        # Unanticipated failure in the route: capture the traceback, then
        # re-raise so the registered exception handlers produce the response.
        duration_ms = (time.perf_counter() - start_time) * 1000
        log.exception(
            "request_failed",
            method=request.method,
            path=request.url.path,
            duration_ms=round(duration_ms, 2),
        )
        raise
    else:
        duration_ms = (time.perf_counter() - start_time) * 1000
        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response
    finally:
        clear_contextvars()
