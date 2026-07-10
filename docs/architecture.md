# py-langid-api: Architecture

## Overview

py-langid-api is a REST API written in Python 3.13 with FastAPI that wraps a
scikit-learn model to detect the language of a short piece of text,
classifying it as English (EN), German (DE), or Italian (IT), and returning
a confidence score alongside the prediction. It exposes two endpoints:
`POST /identify-language` for the prediction itself, and `GET /health` as a
liveness and model-readiness check.

This document is the entry point for anyone who wants to read the code,
understand the choices, or follow a request from HTTP boundary down to the
model and back.

## How the Design Evolved

The project started with `print()` calls for startup messages: no levels,
no structure, no control over output. ADR-005 records the move to
`structlog`, chosen because the request ID tracing feature needs context
(a request ID) bound once and automatically included in every subsequent
log call for that request, which the standard library's logging module has
no built-in mechanism for. The destination went through its own reversal:
the first instinct was to write to a log file, but that makes the app
responsible for rotation, disk space, and paths. The app now emits a
structured stream to stdout only, and the execution environment (Docker,
the deployment platform, a shell redirect) owns routing and storage,
following the 12-factor principle.

Error handling went through a similar narrowing. ADR-004 considered
returning an `ErrorResponse` as a normal value from the route
(`response_model=Union[SuccessModel, ErrorResponse]`), the pattern FastAPI's
own docs show first. It was rejected: a returned object defaults to 200 OK
unless extra machinery sets the status code, and the exception-to-taxonomy
mapping would be duplicated across every route. The chosen strategy raises
typed domain exceptions from the service layer and translates them to
responses through global handlers registered once on the app. Because each
exception subclass carries its own `status_code`, `error_code`, `message`,
and `doc_url` as class attributes, one handler registered on the base
`LanguagePredictionError` catches every subtype through inheritance,
so adding a new error type later is a new subclass, not a new handler.

Configuration moved from scattered assumptions about environment variables
to a typed `Settings` object (ADR-001, ADR-002) backed by pydantic-settings,
validated once at import time so a malformed value fails at startup rather
than at first use, consistent with the project's LBYL-by-construction
approach to configuration.

## Layer Architecture

The codebase separates by concern into schemas, core infrastructure,
routers, and a service layer, with `app/main.py` as the composition root
that wires them together.

```
app/
  main.py            composition root: lifespan, create_app, middleware
  schemas/
    language.py       PredictionInput, PredictionOutput
    responses.py       ErrorResponse
    health.py           HealthResponse
  core/
    config.py          Settings (pydantic-settings)
    dependencies.py     get_model (the DI seam)
    exceptions.py       LanguagePredictionError and subclasses
    handlers.py         validation_exception_handler, language_prediction_error_handler, not_found_handler
    logging.py          setup_logging (structlog configuration)
  routers/
    health.py           GET /health
    language.py          POST /identify-language
  service/
    model.py             predict()
```

### Schemas (`app/schemas/`)

Pydantic models. `PredictionInput` validates the request body (`text`,
stripped of surrounding whitespace, minimum length 1, so an empty or
whitespace-only string is rejected before any route code runs).
`PredictionOutput` validates the success response (`language_code`,
`confidence` constrained to `[0.0, 1.0]`). `ErrorResponse` in
`responses.py` is the single shape every error, regardless of source, is
translated into (ADR-003). `HealthResponse` in `health.py` validates the
`/health` response (`status`, always `"OK"`, and `model_loaded`).

### Core (`app/core/`)

Infrastructure that is not business logic and not a route.

- `config.py`: `Settings`, a `BaseSettings` subclass reading `MODEL_PATH`,
  `LOG_LEVEL`, `LOG_FORMAT` from environment variables or a local `.env`
  file, real environment variables taking precedence. Instantiated once at
  import time so a malformed value raises immediately.
- `dependencies.py`: `get_model`, a one-line function that reads
  `request.app.state.model`. This is the seam FastAPI's dependency
  injection uses to hand the same in-memory model to every route that asks
  for it, and the seam tests substitute a fake model through via
  `app.dependency_overrides`.
- `exceptions.py`: `LanguagePredictionError` and its subclasses
  `ModelUnavailableError` (503) and `PredictionFailedError` (500). Each
  subclass bakes in its own `status_code`, `error_code`, `message`, and
  `doc_url` so raising it takes no arguments at the call site.
- `handlers.py`: `validation_exception_handler` reshapes FastAPI's
  automatic Pydantic validation error into the unified `ErrorResponse`
  shape. `language_prediction_error_handler` is registered on the base
  `LanguagePredictionError` and serves every domain error through
  inheritance, reading the four attributes off whatever exception was
  raised. `not_found_handler` is registered directly on the integer status
  code `404`, since FastAPI raises a plain `HTTPException` itself when no
  route matches, not a domain exception, so there is no
  `LanguagePredictionError` subtype to key a handler off.
- `logging.py`: `setup_logging`, called once from the lifespan. Configures
  the stdlib root logger (a single stdout handler with a pass-through
  formatter, since structlog has already rendered the final line) and the
  structlog processor chain (context merging, level, ISO timestamp, and
  either `JSONRenderer` or `ConsoleRenderer` depending on `LOG_FORMAT`).

### Routers (`app/routers/`)

Thin route handlers. `health.py`'s `get_health` reads `app.state.model`
directly (not through the `get_model` dependency) so the readiness check
stays independent of the prediction path, and always returns 200: the
model's state is data in the body, not a status code, because a successful
health check means the check itself ran. `language.py`'s
`identify_language` takes a validated `PredictionInput`, gets the model
through `Depends(get_model)`, and returns whatever `predict()` returns. It
contains no `try/except`; prediction errors propagate to the registered
handlers.

### Service (`app/service/`)

`predict()` in `model.py` is the one place business logic lives: it raises
`ModelUnavailableError` if the model is `None`, calls `model.predict()` and
`model.predict_proba()` inside a `try/except`, and wraps any exception from
the model in `PredictionFailedError` via `raise ... from e` so the original
cause is preserved in the traceback and shows up in the log output without
the handler reading `__cause__` directly. The service knows nothing about
HTTP: it raises plain domain exceptions, never `HTTPException`, which keeps
it directly testable without any FastAPI machinery.

### Composition Root (`app/main.py`)

`create_app(routers, exception_handlers)` is a factory: it takes a list of
routers and a mapping of exception types to handlers and wires them in
declaratively, instead of scattering `include_router` and
`add_exception_handler` calls. The module-level `app` is the one instance
actually served; `create_app` itself is what test_lifespan.py calls
directly to build fresh app instances against a monkeypatched
`settings.model_path`, without needing a running server.

The `lifespan` context manager runs once at startup and once at shutdown:
it calls `setup_logging`, then loads the pickled model with EAFP (`try`
around `open` and `pickle.load`, not a preceding existence check, since
checking and opening cannot be meaningfully separated for a file that could
disappear between the two steps). On `FileNotFoundError` or any other
exception, `app.state.model` is left `None` so the dependency and the
service both observe the absence and the request path resolves to
`ModelUnavailableError` rather than crashing.

The `logging_middleware` wraps every request: it generates a request ID,
binds it via `structlog.contextvars` so every log line produced during that
request's handling includes it automatically, logs `request_started` at
DEBUG and `request_completed` at INFO with the duration, and re-raises any
exception after logging `request_failed` so the registered handlers still
produce the response. `clear_contextvars` in the `finally` block prevents
the request ID from leaking into the next request handled by the same
worker.

## Key Design Decisions

Full context for each decision lives in `docs/adr/`, indexed in
`docs/adr/index.md`. Summarized here in relation to the code:

- **ADR-001** picks FastAPI specifically for the combination of automatic
  OpenAPI generation, built-in Pydantic validation, and the lifespan plus
  dependency injection pair that loads the model once and hands the same
  instance to every route, which is what `create_app`, `lifespan`, and
  `get_model` implement together.
- **ADR-002** and the LBYL/EAFP split explain why `lifespan` uses a bare
  `try/except` around the pickle load (EAFP) while `Settings` validates
  eagerly at import time (LBYL by construction).
- **ADR-003** is the shape every `ErrorResponse` in `app/schemas/responses.py`
  implements, and the taxonomy that decides which status codes this API can
  actually produce (documented, with examples, in `docs/errors.md`).
- **ADR-004** is why routes in `app/routers/` contain no `try/except` and
  why `app/core/handlers.py` has exactly one handler for every domain
  exception subtype.
- **ADR-005** is why `app/core/logging.py` configures structlog to write
  to stdout only, and why `logging_middleware` binds a request ID via
  contextvars instead of passing it explicitly into every log call.
- **ADR-006** is why the model is injected through `get_model` rather than
  imported directly: that seam is what `tests/conftest.py`'s
  `override_model_none` and `override_model_raises` fixtures substitute a
  fake model through, without touching route code.

## Request Lifecycle

### POST /identify-language, successful prediction

1. `logging_middleware` generates a request ID, binds it via
   `bind_contextvars`, and logs `request_started` at DEBUG.
2. FastAPI parses the JSON body against `PredictionInput`. The `text`
   field is stripped of whitespace and checked for `min_length=1`. If this
   fails, `RequestValidationError` is raised before `identify_language`
   ever runs, see the failure path below.
3. `identify_language` runs. `Depends(get_model)` reads
   `request.app.state.model`, set once at startup by `lifespan`.
4. `identify_language` calls `predict(input, model)`. The service checks
   `model is None` (it is not, in this path), then calls
   `model.predict([input.text])` and `model.predict_proba([input.text])`
   inside a `try/except`, rounds the confidence to 3 decimals, and
   constructs a `PredictionOutput`.
5. FastAPI serializes `PredictionOutput` against `response_model` and
   returns 200.
6. `logging_middleware` logs `request_completed` at INFO with the status
   code and duration, then `clear_contextvars` runs in `finally`.

### POST /identify-language, validation failure

1. through 2. as above, but Pydantic validation fails (empty string,
   missing field, or wrong type).
2. `validation_exception_handler` is invoked by FastAPI's exception
   dispatch, before `identify_language` runs, before the model is ever
   reached. It reads `exc.errors()[0]["msg"]`, logs `validation_error` at
   WARNING (a client mistake, not a server failure), and returns a 422
   `ErrorResponse` with `error_code="validation_error"`.

### POST /identify-language, model unavailable

1. through 3. as the successful path, but `lifespan` left
   `app.state.model` as `None` (the model file was missing or failed to
   unpickle at startup).
2. `predict()` raises `ModelUnavailableError()` immediately, before
   calling `model.predict()`.
3. `language_prediction_error_handler`, registered on the base
   `LanguagePredictionError`, catches it through inheritance, logs
   `prediction_error` at ERROR (a server-side condition), and returns 503
   with `error_code="model_unavailable"`.

### POST /identify-language, prediction fails unexpectedly

1. through 3. as the successful path, but `model.predict()` or
   `model.predict_proba()` raises inside the service's `try` block.
2. `predict()` catches the exception and re-raises
   `PredictionFailedError()` via `raise ... from e`, preserving the
   original exception as `__cause__`.
3. `language_prediction_error_handler` detects `PredictionFailedError`
   specifically and calls `log.exception` instead of `log.error`, so the
   chained cause is captured in the log output via Python's own traceback
   rendering, without the handler reading `__cause__` directly. Returns
   500 with `error_code="prediction_failed"`.

### GET /health

Reads `app.state.model` directly (bypassing `get_model`) and always
returns 200 with `model_loaded` reflecting whether `lifespan` succeeded in
loading the model. The endpoint reports state; it does not act on it,
keeping that decision the prediction route's responsibility.

### Any path, no matching route

1. `logging_middleware` generates a request ID and logs `request_started`
   at DEBUG, same as any other request; routing happens inside the call it
   wraps.
2. FastAPI finds no matching route and raises `HTTPException(status_code=404)`
   itself, before any application route code runs.
3. `not_found_handler`, registered on the integer `404` rather than an
   exception type, logs `not_found` at WARNING with the requested path and
   returns a fixed 404 `ErrorResponse` with `error_code="not_found"`.
4. `logging_middleware` logs `request_completed` at INFO with status 404,
   then `clear_contextvars` runs in `finally`.

## Testing

Tests use `pytest` and FastAPI's `TestClient` (built on `httpx2`), run
in-process with no real server. Full reasoning in ADR-006; summarized here
against the actual suite:

- `tests/test_health.py` covers the one behavior that matters for
  `/health`: that `model_loaded` reflects the real state, in both
  directions, using the `restore_model_state` fixture so a test that
  mutates `client.app.state.model` directly does not leak into later
  tests (the `client` fixture is session-scoped).
- `tests/test_prediction.py` covers the prediction endpoint across its
  outcomes: success with a real model, empty and whitespace-only text
  (422 before the model is touched), model unavailable (503, via the
  `override_model_none` fixture), and prediction failure (500, via
  `override_model_raises`, a fake model whose `predict` raises
  `ValueError`).
- `tests/test_lifespan.py` drives `create_app` directly (not the shared
  `app` instance) with `monkeypatch.setattr(settings, "model_path", ...)`,
  covering both the present-file and missing-file startup paths.
- `tests/test_not_found.py` covers the unmatched-route path: an unknown
  path returns 404 with the unified `ErrorResponse` shape and
  `error_code="not_found"`.

The fixtures in `tests/conftest.py` never fake the response under test,
only the model dependency: `override_model_none` and
`override_model_raises` substitute a fake through
`app.dependency_overrides[get_model]`, so the real routing, validation,
and error-handling code runs in every test, and only the model's behavior
is controlled. Middleware and logging have no dedicated tests: the
middleware's one behavior that matters, that an exception passing through
is re-raised rather than swallowed, is already exercised transitively by
every 500 and 503 test, since the middleware would need to re-raise for
those responses to reach the test client at all.

## Python Conventions

- **LBYL for validation at boundaries, EAFP for I/O.** `Settings` validates
  environment variables eagerly at import time (LBYL by construction, since
  pydantic-settings raises before the app serves anything). `lifespan`
  wraps the pickle load in `try/except` rather than checking
  `Path.exists()` first (EAFP), since the file could disappear or become
  unreadable between a check and the open, so checking first would not
  actually be safer.
- **`None` for expected absence, exceptions for unexpected failure.**
  `app.state.model` being `None` after a failed load is expected absence,
  checked explicitly in `predict()`. A model that raises during prediction
  is unexpected failure, caught and re-raised as a typed exception, not
  represented as `None`.
- **Exceptions carry their own HTTP mapping.** Each `LanguagePredictionError`
  subclass is a class-attribute bundle of `status_code`, `error_code`,
  `message`, and `doc_url`, so the mapping from domain error to HTTP
  response lives on the exception, not scattered across raise sites or
  duplicated in the handler. This is what lets one handler, registered on
  the base class, serve every subtype through Python's normal exception
  inheritance and dispatch.
- **`raise ... from e` for chained causes.** `PredictionFailedError` is
  always raised with `from e` in the service, so the underlying sklearn
  exception is preserved as `__cause__`. The handler relies on
  `log.exception` to capture `sys.exc_info()` and let Python's traceback
  rendering walk the chain, rather than reading `__cause__` directly,
  keeping the logging call ignorant of exception internals.
- **Dependency injection as the test seam.** `get_model` is a real
  indirection, not a convenience wrapper: routes ask for the model through
  `Depends(get_model)` rather than importing `app.state` directly, which is
  the same seam `app.dependency_overrides` uses in tests to substitute a
  fake model without touching route code.
