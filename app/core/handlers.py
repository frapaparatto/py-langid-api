import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .exceptions import LanguagePredictionError, PredictionFailedError
from ..schemas.responses import ErrorResponse

log = structlog.get_logger()


async def validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Reshape FastAPI's automatic validation error (the default 422 with a
    loc/msg/type structure) into the unified ErrorResponse shape.

    The exc parameter is typed as the broad Exception, not
    RequestValidationError, to satisfy the handler slot's expected
    signature (parameter contravariance: a handler accepting a narrower
    type cannot fill a slot that promises any Exception). The
    assert isinstance narrows it back to RequestValidationError for the
    rest of the body, and is always true given how FastAPI dispatches.

    Builds an ErrorResponse (the shape contract), then wraps it in a
    JSONResponse (the transport carrying status code and body). The first
    error message from exc.errors() is surfaced as the message.
    """
    assert isinstance(exc, RequestValidationError)
    message = exc.errors()[0]["msg"]
    # WARNING, not ERROR: a validation error is a client mistake (4xx),
    # expected operation, not a server-side failure. request_id is added
    # automatically from the bound context.
    log.warning("validation_error", message=message)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_code="validation_error",
            message=message,
            doc_url="https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#validation_error",
        ).model_dump(),
    )


async def language_prediction_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Handle every domain prediction error with one handler.

    Registered on the base LanguagePredictionError, so by inheritance it
    catches every subtype (ModelUnavailableError, PredictionFailedError,
    and any future one). Each exception carries its own status_code,
    error_code, message, and doc_url, so the handler reads them and builds
    the response.

    The exc parameter is typed as the broad Exception, not
    LanguagePredictionError, to satisfy the handler slot's expected
    signature (parameter contravariance). The assert isinstance narrows it
    back for the rest of the body, and is always true given how FastAPI
    dispatches this handler only for LanguagePredictionError and subtypes.

    Both domain errors are server-side (5xx), so both log at ERROR.
    PredictionFailedError additionally carries a chained cause
    (exc.__cause__, the underlying sklearn exception preserved by the
    service's `raise ... from e`), so it uses log.exception to capture that
    traceback. ModelUnavailableError has no hidden cause, so plain
    log.error is enough. request_id is added automatically from the
    bound context.
    """
    assert isinstance(exc, LanguagePredictionError)
    if isinstance(exc, PredictionFailedError):
        log.exception(
            "prediction_error",
            error_code=exc.error_code,
            status=exc.status_code,
        )
    else:
        log.error(
            "prediction_error",
            error_code=exc.error_code,
            status=exc.status_code,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            doc_url=exc.doc_url,
        ).model_dump(),
    )
