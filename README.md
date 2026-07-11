# py-langid-api

A lightweight REST API for language detection, built with FastAPI and Docker.

## Overview

py-langid-api wraps a scikit-learn model behind a small HTTP surface: a
prediction endpoint that classifies a short piece of text as English (EN),
German (DE), or Italian (IT) with a confidence score, and a health endpoint
that reports whether the model is loaded and ready. The model is loaded
once at startup and shared across every request through FastAPI's
dependency injection, never reloaded per request.

### Features

- **`POST /identify-language`**: takes `{"text": "..."}`, returns
  `{"language_code": "...", "confidence": 0.0-1.0}`. Confidence is reported
  as data, not judged: a low score is still a successful response, and the
  caller decides what threshold is acceptable for its own use.
- **`GET /health`**: always returns 200 with `{"status": "OK",
  "model_loaded": true|false}`. Liveness and model readiness are reported
  as data in the body, not as the status code.
- **Unified error taxonomy**: every error response, validation failure,
  unavailable model, or unexpected prediction failure, shares one JSON
  shape (`error_code`, `message`, `doc_url`), documented in full in
  `docs/errors.md`.
- **Structured logging**: every request is logged with a bound request ID
  that appears on every log line produced while that request is handled,
  as JSON in production or readable console output in development.

## Architecture

The codebase separates by concern: Pydantic schemas validate the HTTP
boundary, a core module holds configuration, the dependency-injection seam,
the exception taxonomy, error handlers, and logging setup, routers stay
thin, and one service function holds the actual prediction logic. `app/main.py`
is the composition root: it builds the app from a list of routers and a
mapping of exception handlers, and owns the lifespan that loads the model
once at startup.

- **`app/schemas`**: `PredictionInput`, `PredictionOutput`, `ErrorResponse`.
  Pydantic models, no logic beyond validation.
- **`app/core`**: `Settings` (pydantic-settings, validated at import time),
  `get_model` (the dependency-injection seam that also serves as the test
  substitution point), the `LanguagePredictionError` exception hierarchy,
  the three registered exception handlers (validation, domain prediction
  errors, not found), and structlog configuration.
- **`app/routers`**: `health.py` and `language.py`. Routes validate nothing
  themselves (Pydantic already did) and contain no `try/except`; errors
  propagate to the registered handlers.
- **`app/service`**: `predict()`, the one place business logic lives, raises
  typed domain exceptions and knows nothing about HTTP.

The model is injected, not imported: routes ask for it through
`Depends(get_model)`, which reads `app.state.model`. This is the same seam
tests use to substitute a fake model via `app.dependency_overrides`, without
touching route code.

Full architecture reference, including a request-by-request walkthrough of
each outcome (success, validation failure, model unavailable, prediction
failure), lives in `docs/architecture.md`.

## Building and Running

### Prerequisites

* Python 3.13
* [uv](https://docs.astral.sh/uv/) for dependency management
* Docker and docker-compose, for the containerized run

### Local run

First create a virtual environment: a private folder (`.venv`) that holds
just this project's Python packages, kept separate from anything else
installed on your computer so this project can never conflict with, or be
affected by, other Python projects. Then install the dependencies into it,
and finally run the app. Each line below is a command: run it in a terminal,
from the directory containing this repository, waiting for each to finish
before running the next.

```bash
uv venv
uv sync
uv run uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for the interactive OpenAPI
documentation, or POST to `/identify-language` with a JSON body of the form
`{"text": "some sentence"}`.

`model.pkl` must be present at the path configured by `MODEL_PATH` (default
`./model.pkl`, relative to the working directory). If it is missing at
startup, the app still starts, but `/identify-language` responds 503 until
a valid model is in place; see `model_unavailable` in `docs/errors.md`.

### Docker

```bash
docker compose up --build
```

Builds the image from the `Dockerfile` (`python:3.13-slim-trixie`, dependencies
installed via `uv sync --locked`) and runs `uvicorn` bound to `0.0.0.0:8000`,
with `MODEL_PATH` pointed at the in-container model path via
`docker-compose.yml`.

### Run the test suite

```bash
uv run pytest
```

## Configuration

Configuration is read from environment variables through a typed
`Settings` object (`app/core/config.py`), backed by pydantic-settings. A
local `.env` file is also read if present; real environment variables take
precedence. See `.env.example` for the full list with defaults:

```ini
MODEL_PATH=./model.pkl
LOG_LEVEL=INFO
LOG_FORMAT=json
```

An invalid value (an unknown `LOG_LEVEL`, for instance) fails validation at
import time, so the app never starts in a half-configured state.

## Error Handling

Every error response is unified into one shape by a global exception
handler, regardless of where it originated:

```json
{
  "error_code": "validation_error",
  "message": "text field cannot be empty",
  "doc_url": "https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#validation_error"
}
```

The full taxonomy (`validation_error` / 422, `not_found` / 404,
`model_unavailable` / 503, `prediction_failed` / 500), with example
responses for each, is documented in `docs/errors.md`.

## Testing

Tests are written with `pytest` and FastAPI's `TestClient`, run in-process
against the real app with no server process. The model is the only thing
ever faked, through the same dependency-injection seam the app uses in
production (`app.dependency_overrides`); everything else, validation,
routing, error handling, response shaping, is exercised for real.

- `tests/test_health.py`: the model-readiness behavior, in both states.
- `tests/test_prediction.py`: the prediction endpoint across every outcome,
  success, validation failure, model unavailable, prediction failure.
- `tests/test_lifespan.py`: model loading at startup, both with the file
  present and missing.
- `tests/test_not_found.py`: an unmatched route returns the unified 404
  error shape.

The judgment behind what is and is not tested, in particular why
middleware and logging have no dedicated tests, is recorded in ADR-006.

## Architecture Decision Records

All architecture decision records live in `docs/adr/`. The index is
`docs/adr/index.md`.

## AI Usage

This project was built as a learning exercise under the AI usage protocol
defined in `CLAUDE.md`.

- **Socratic reasoning**: when stuck on a design or implementation problem, AI
was to be consulted only after independent effort, using questions that
challenge assumptions rather than supplying answers, with AI generating no
code in that mode.
- **Architecture review after an independent position**: AI reviewed a design
only after a position was already formed and, in most cases, implemented
once, never proposing the architecture first. The repository's ADRs are
themselves written in that voice, first person, documenting a decision I
reached (including, in ADR-005, naming an earlier approach that was tried
and deliberately reversed). The concrete instances in this project are the
error handling strategy (ADR-002), the error propagation strategy
(ADR-004), the logging strategy (ADR-005), and the testing strategy
(ADR-006): each records a decision reached first, with AI entering
afterward for feedback.
- **Docstrings and comments**: for the documentation embedded in the code, AI's
role was limited to correcting grammar and lightly expanding a first draft
I wrote. In each case I wrote the initial docstring or comment, and AI
refined the wording after a short discussion. The reasoning expressed in
them is mine.
- **What AI did not do**: it did not choose the architecture, decide the error
taxonomy, or decide what to test, first. Debugging in this project was
manual, root cause first, per the same CLAUDE.md protocol.
- **Documentation written by AI**: the study notes in `docs/learning/` (on
logging, error handling, and related topics) were written by AI only after
a discussion in which my own understanding was stated, questioned, and
corrected until verified. The reasoning and the ideas in those notes are
mine; AI's contribution there was clearer prose, not the underlying
understanding.

## Future Improvements

- Rate limiting (`429 Too Many Requests`): not yet implemented, so not currently documented as a producible status code.
- Request ID tracing beyond the current per-request log correlation: surface the request ID back to the client (for example as a response header) so a caller can reference it when reporting an issue.
- Deployment to a Docker-native PaaS.
