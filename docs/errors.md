# Errors

All error responses share a single JSON shape, regardless of error type or origin:

```json
{
  "error_code": "string",
  "message": "string",
  "doc_url": "string"
}
```

`error_code` is a machine-readable category. `message` is a human-readable reason. `doc_url` links to documentation for that error.

> **Note on `doc_url` values:** Each error's `doc_url` links directly to its specific section on this page (`#validation_error`, `#model_unavailable`, `#prediction_failed`).

## Contents

- [validation\_error (422)](#validation_error)
- [model\_unavailable (503)](#model_unavailable)
- [prediction\_failed (500)](#prediction_failed)


## validation_error

**HTTP status:** 422 Unprocessable Entity

Raised when the request body fails Pydantic validation before the route runs. This covers three conditions:

- The `text` field is missing from the request body entirely.
- The `text` field is empty (`""`) or whitespace-only, whitespace is stripped before length validation, so `"   "` fails the same way as `""`.
- The `text` field is the wrong type (not a string).

The `message` field in the response comes directly from Pydantic's first validation error (`exc.errors()[0]["msg"]`), so its exact wording varies by condition.

**Example response: empty or whitespace-only `text`:**

```json
{
  "error_code": "validation_error",
  "message": "String should have at least 1 character",
  "doc_url": "https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#validation_error"
}
```

**Example response: missing `text` field:**

```json
{
  "error_code": "validation_error",
  "message": "Field required",
  "doc_url": "https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#validation_error"
}
```


## model_unavailable

**HTTP status:** 503 Service Unavailable

Raised when the language model is not loaded. This occurs when model loading failed at startup (file not found, or any exception during `pickle.load`), which leaves `app.state.model` as `None`. The prediction service checks for `None` on every request and raises this error before attempting prediction.

**Example response:**

```json
{
  "error_code": "model_unavailable",
  "message": "The model is not loaded or unavailable.",
  "doc_url": "https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#model_unavailable"
}
```


## prediction_failed

**HTTP status:** 500 Internal Server Error

Raised when the model is loaded but prediction returns no usable result: specifically, when `model.predict()` or `model.predict_proba()` returns a value from which `language_code` or `confidence` is `None`. The message is a fixed default string.

**Example response:**

```json
{
  "error_code": "prediction_failed",
  "message": "Prediction failed unexpectedly.",
  "doc_url": "https://github.com/frapaparatto/py-langid-api/blob/main/docs/errors.md#prediction_failed"
}
```
