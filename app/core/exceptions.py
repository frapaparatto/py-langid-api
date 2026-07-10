class LanguagePredictionError(Exception):
    """
    Base class for all domain-specific prediction errors.

    Each subclass bakes in its own status_code, error_code, and doc_url so
    that raising it requires no arguments at the call site (an optional
    message override is allowed). This keeps the full taxonomy mapping
    (status code included) inside the exception class instead of scattered
    across raise sites or split between the exception and its handler.

    These remain plain domain exceptions: they are raised by the service
    layer, which knows nothing about HTTP beyond carrying these values. A
    single registered handler reads status_code, error_code, message, and
    doc_url off the exception and builds the HTTP response. The handler does
    not decide the mapping; the exception owns it.

    super().__init__(message) is called so the exception behaves like a
    proper Python exception: it stores the message in args, so str(exc),
    tracebacks, and log lines show a meaningful message rather than an empty
    one. This serves the Python-level representation (logs, debugging),
    separate from the custom fields that serve the HTTP response.
    """

    status_code: int = 500

    def __init__(self, error_code: str, message: str, doc_url: str):
        self.error_code = error_code
        self.message = message
        self.doc_url = doc_url
        super().__init__(message)


class ModelUnavailableError(LanguagePredictionError):
    """
    Raised when the model is not loaded or otherwise unavailable.

    Maps to HTTP 503. This occurs when model loading failed at startup,
    so app.state.model is None.
    """

    status_code = 503

    def __init__(self, message: str = "The model is not loaded or unavailable."):
        super().__init__(
            error_code="model_unavailable",
            message=message,
            doc_url="https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#model_unavailable",
        )


class PredictionFailedError(LanguagePredictionError):
    """
    Raised when prediction fails unexpectedly.

    Maps to HTTP 500. This covers the case where the model is loaded but
    model.predict() or model.predict_proba() raises during prediction.
    """

    status_code = 500

    def __init__(self, message: str = "Prediction failed unexpectedly."):
        super().__init__(
            error_code="prediction_failed",
            message=message,
            doc_url="https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#prediction_failed",
        )
