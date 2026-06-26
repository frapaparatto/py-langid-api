from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from typing import Callable, Any, Coroutine
import pickle

from .routers import health, language
from .core.exceptions import LanguagePredictionError
from .core.handlers import (
    validation_exception_handler,
    language_prediction_error_handler,
)


ExceptionHandler = Callable[[Request, Any], Coroutine[Any, Any, Response]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once at startup, before the app accepts requests,
    # so every request reuses the same in-memory object.
    # The path is a temporary placeholder; configuration replaces it later.
    print("Application startup: loading model...")
    try:
        with open("./model.pkl", "rb") as file:
            app.state.model = pickle.load(file)
        print("Model loaded successfully.")
    except FileNotFoundError:
        # Loading failed: leave the model unset so the dependency can
        # detect it and the service can raise ModelUnavailableError (503).
        print("Model file not found.")
        app.state.model = None
    except Exception as e:
        print(f"Error loading model during startup: {e}")
        app.state.model = None
    yield
    # Shutdown: release the model.
    print("Application shutdown: cleaning up resources...")
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
