# Architecture Decision Records

This index lists all decision records for py-langid-api. Each entry summarizes the decision in one or two sentences.

### ADR-001: Tech Stack

FastAPI over Flask for automatic OpenAPI generation, built-in Pydantic validation, and lifespan plus dependency injection as a fit for loading the model once and handing it to every route. structlog for structured, context-bindable logging; pydantic-settings for typed, fail-fast configuration; pytest with httpx2 for in-process testing; uv and ruff for tooling; Docker and docker-compose for containerized deployment.

### ADR-002: Error Handling Strategy

Four mechanisms, each with one role: `assert` for programmer errors, exceptions (`ValueError`, `RuntimeError`, or a precise built-in) for rare runtime failures, `None` for expected absence, and Pydantic validation at the HTTP boundary. LBYL is used where checking and acting can be cleanly separated; EAFP is used for I/O where the check and the action cannot be, such as loading the pickled model file.

### ADR-003: Error Response Shape

Every error response, regardless of source, is unified into one shape: `error_code`, `message`, `doc_url`, with `doc_url` pointing to the matching anchor in `docs/errors.md`. The status code taxonomy is documented by who produces it: automatic (FastAPI/Pydantic), manual, or stretch-dependent (only real if the feature exists).

### ADR-004: Error Propagation Strategy

Errors are raised as typed domain exceptions (`ModelUnavailableError`, `PredictionFailedError`) that carry their own `status_code`, `error_code`, `message`, and `doc_url`, and are translated into responses by global handlers registered once on the app, rather than being caught and returned per route. A single handler registered on the base `LanguagePredictionError` catches every subtype through inheritance.

### ADR-005: Logging Strategy

structlog renders structured events (JSON in production, console in development) at three levels of granularity: lifecycle, request/response, and errors. Logs are written to stdout only, following the 12-factor principle that an app should emit a stream and let the environment own routing and storage, a deliberate reversal of an earlier file-writing approach.

### ADR-006: Testing Strategy

Tests fake the dependency (the model), never the response, and are allocated by risk: the prediction endpoint's error paths and the health endpoint's readiness reporting are tested thoroughly, while trivial paths and observability concerns (logging, middleware) are not given dedicated tests since the middleware's one important behavior is already covered transitively by the error-path tests. Unit tests isolate branches a real model cannot easily trigger; integration tests exercise the real request-response pipeline with only the model faked.
