# Error Handling Reference

A single reference for the error handling design: the taxonomy, the conceptual model, and the design decisions. Meant to be read alongside the FastAPI docs while implementing.


## The error response shape (from ADR-003)

Every error response, whatever its source, is unified into one consistent JSON shape through a global handler:

```json
{
  "error_code": "validation_error",
  "message": "text field cannot be empty",
  "doc_url": "https://github.com/frapaparatto/py-langid-api#errors"
}
```

- **`error_code`**: a machine-readable category the client can branch on.
- **`message`**: a human-readable reason.
- **`doc_url`**: a link to documentation about that specific error, so the response itself is informative.

The `doc_url` value above is illustrative; the real target is finalized once the documentation structure exists.


## Status code vs error code

These are two different things and both appear in a failed response.

- **Status code** (`422`, `500`, `503`): the broad HTTP category, standardized across the whole web. A generic client can react to it without understanding the app. It lives in the HTTP status line, not in the JSON body.
- **Error code** (`validation_error`, `model_unavailable`): your own application-specific identifier, inside the JSON body. Not standardized anywhere; you invent and document it.

The status code is for code (broad category, machine-reactable). The body is for humans and for finer-grained logic. They are redundant by design: a client can branch on the status code alone, or read the body for the specific reason.


## The taxonomy (the table to implement against)

Each code is marked by who produces it: **automatic** (FastAPI emits it without custom code), **manual** (must be implemented), or **stretch-dependent** (only occurs if a stretch feature is built).

| Condition | Status | error_code | Who produces it |
|---|---|---|---|
| Invalid or malformed input | 422 | validation_error | automatic (Pydantic) |
| Malformed/unparseable body | 400 | validation_error | automatic (FastAPI) |
| Unknown route | 404 | not_found | automatic (FastAPI) |
| Model not loaded / not ready | 503 | model_unavailable | manual (needs readiness check) |
| Prediction fails unexpectedly | 500 | prediction_failed | manual |
| Rate limit exceeded | 429 | rate_limit_exceeded | stretch-dependent |

The core three for this project, the ones to implement first:

- model not loaded → `503` → `model_unavailable`
- prediction fails unexpectedly → `500` → `prediction_failed`
- input validation (automatic, via Pydantic) → `422` → `validation_error`

Honesty rule: do not document a code the API cannot actually produce. Before finalizing, remove any manual/stretch codes that are not implemented.


## The two layers of error handling

There are two distinct places errors get handled. Both produce the same `ErrorResponse`; the difference is where the mapping lives and what triggers it.

### Layer 1: global handlers for broad, automatic cases

Some errors should be handled once, app-wide, not in every route:

- **Validation errors**: Pydantic produces a default 422 with a `loc`/`msg`/`type` structure. A handler that overrides the validation error reshapes that default into the unified `ErrorResponse` with `error_code` validation_error.
- **Unexpected crashes**: a catch-all handler turns any unhandled exception into a `500` with `error_code` prediction_failed, so a raw traceback never reaches the client.

These are registered once on the app and apply everywhere. No per-route error code.

### Layer 2: typed domain exceptions for specific, named conditions

The service raises **plain domain exceptions** (not HTTP-aware), for example a model-not-loaded error or a prediction-failed error. A handler registered for each exception type maps it to its taxonomy entry (status code, error code, the `ErrorResponse` shape).

- The service raises the typed exception and knows nothing about HTTP.
- The router does not need a try/except; the exception propagates.
- The registered handler catches that specific type and produces the response.

This keeps routers clean and centralizes the mapping in one place per exception type.


## The decision rule: which layer handles what

- **Broad or automatic** (validation, totally unexpected crashes) → global handler, written once.
- **A specific domain condition the code can name** (model unavailable, prediction failed for a known reason) → a registered handler for that exception type.


## Design decisions behind this

- **Unify everything into one shape.** Pydantic's automatic errors and your own raised errors produce different default shapes. Reshaping both into one `ErrorResponse` keeps the API consistent for clients.
- **The service stays HTTP-agnostic.** It raises plain exceptions, never `HTTPException`. This keeps it reusable outside FastAPI and testable in isolation. Only the router/handlers translate to HTTP. (From ADR-002: the service speaks domain, the boundary speaks HTTP.)
- **Validate structure, not meaning.** Empty or whitespace-only input is rejected at validation (422). Semantically thin input (only digits, only punctuation) is passed to the model, which returns low confidence. This follows the real-world ML API convention and keeps the design coherent.
- **Confidence is not an error.** A low-confidence prediction is a successful response. The API returns the label and the score; the consumer applies its own business rules to decide what confidence is acceptable. Baking a threshold into the API would impose one judgment on every consumer.
- **Design the table before the handlers.** Once the exception-type-to-status-to-error-code table exists, the handlers write themselves. The table is the taxonomy made concrete.


## Two strategies for returning errors (and why this design picks one)

There are two genuinely different ways to send an error, and they are easy to conflate.

**Strategy A: return the error model from the route.**

- The route has its own `try/except`, and on error it `return`s an `ErrorResponse` as a normal return value (with `response_model=Union[...]` on the decorator).
- Because it is a returned Pydantic object, the automatic `response_model` step applies: FastAPI validates and serializes it.
- Error handling lives inside each route.
- Two real drawbacks: a returned object defaults to **200 OK** (so an error would be sent with a success status unless extra machinery is added), and the error handling is duplicated across every route.

```python
@app.post("/predict", response_model=Union[PredictionOutput, ErrorResponse])
def predict(input: PredictionInput, model = Depends(get_model)):
    try:
        if model is None:
            return ErrorResponse(error_code="model_unavailable", message="...", doc_url="...")
        result = model.predict([input.text])[0]
        return PredictionOutput(language_code=result, confidence=...)
    except Exception:
        return ErrorResponse(error_code="prediction_failed", message="...", doc_url="...")
```

**Strategy B: raise exceptions, handle them globally (this project's choice).**

- The route has no `try/except`; it returns the success output (`PredictionOutput`) only.
- Errors are raised (by the service) and caught by registered handlers, which return a `JSONResponse`.
- Error handling lives in one place, outside the routes.
- The `JSONResponse` sets the correct status code (503, 500, 422) cleanly, and routes stay focused on the happy path.

```python
# route: only the happy path
@app.post("/predict", response_model=PredictionOutput)
def predict(input: PredictionInput, model = Depends(get_model)):
    return run_prediction(input, model)

# service: raises plain domain exceptions, no HTTP
def run_prediction(input, model):
    if model is None:
        raise ModelUnavailableError()
    ...
    return PredictionOutput(language_code=..., confidence=...)

# handler (registered once on the app): maps the exception to a response
async def model_unavailable_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content=ErrorResponse(
            error_code=exc.error_code, message=exc.message, doc_url=exc.doc_url
        ).model_dump(),
    )
```

The FastAPI docs show Strategy A only to illustrate returning different model types, and explicitly note that real error handling would normally use raise/handle, which is Strategy B. So Strategy B is the recommended production pattern.

Both strategies construct the `ErrorResponse` manually. The difference is what happens after: Strategy A leans on `response_model` to serialize it (but loses easy status-code control), while Strategy B wraps it in a `JSONResponse` (gaining status-code control, doing the serialization wrap by hand).


## Why handlers build ErrorResponse manually (JSONResponse vs response_model)

A key fact that explains the handler code: **`response_model` does not apply to handler responses, and it does not apply when a `JSONResponse` is returned directly.**

- `response_model` only governs the success path of a route: it validates and filters what the path operation function returns. Handlers are not path operations, so it never runs on them.
- Returning a `Response` subclass like `JSONResponse` means "I have built the final response myself, send it as-is." FastAPI does not run `response_model` validation or filtering on it.

So nothing automatically guarantees an error's shape. That is why handlers build `ErrorResponse(...).model_dump()` by hand: constructing the `ErrorResponse` validates the fields (right types, all present) at construction time, then `.model_dump()` turns it into a dict, then `JSONResponse` carries it with the chosen status code.

The result: the success path gets automatic shape-enforcement via `response_model`; the error path gets manual shape-enforcement via constructing `ErrorResponse` in the handler, because returning a `JSONResponse` opts out of the automatic machinery. Routing every error through `ErrorResponse` keeps the shape consistent and gives a single source of truth, the same guarantee `response_model` gives the success path, enforced manually.


## Registering handlers, and the mechanisms involved

Handlers are registered on the app, not declared per route. Three related mechanisms exist:

- **`@app.exception_handler(SomeError)`**: the decorator form. Registers a handler for an exception type. It needs the `app` at module level, so it does not fit a factory cleanly.
- **`app.add_exception_handler(SomeError, handler)`**: the non-decorator form, the same thing as a method call. It works inside a factory, which avoids the circular-import problem.
- **`exception_handlers=` on `FastAPI(...)`**: a dict passed at construction. Passing it in parallels passing routers in: both are wired declaratively.


## The handler type signature, read piece by piece

The `exception_handlers` parameter is typed (simplified) as:

```python
dict[int | type[Exception], Callable[[Request, Any], Coroutine[Any, Any, Response]]] | None
```

Reading it outside in:

- The whole thing is **`... | None`**: the parameter is optional.
- **`dict[KEY, VALUE]`**: a mapping.
- **Keys: `int | type[Exception]`**. A key is either an **integer status code** (register a handler for "any 404", for example) or an **exception class** (register a handler for that type). This project uses exception-class keys.
- **Values: `Callable[[Request, Any], Coroutine[Any, Any, Response]]`**. A handler is a callable that:
  - takes two parameters, a **`Request`** and the exception (typed `Any`);
  - returns a **`Coroutine[Any, Any, Response]`**.

The return type is a `Coroutine`, not a plain `Response`, because handlers are **`async def`**. Calling an `async def` returns a coroutine (an awaitable), and FastAPI awaits it to get the `Response`. In `Coroutine[Any, Any, Response]`, only the last parameter (`Response`) is the meaningful one; the first two are coroutine-machinery details read as `Any`.

This is why handlers must be `async`: the interface FastAPI awaits demands it. That is different from route and service functions, where the async-versus-sync choice depends on whether the function does awaitable I/O.


## Why a specific exception type in the handler trips the type checker

This is the Pyright error, and it comes from how function parameters interact with types.

A type hint on a parameter is a **promise about what the function accepts**. Writing `def handler(request, exc: ModelUnavailableError)` promises "this function handles a `ModelUnavailableError` (or any subclass of it)."

The handler slot in the dict, however, expects a function whose `exc` is the **base** `Exception` (or `Any`). The slot's promise is "I might pass you any `Exception`."

Now the mismatch:

- The **slot** demands: a function that can accept any `Exception`.
- A **specific handler** promises: I only accept `ModelUnavailableError`.

These do not match, and the direction is the key point. It feels like they should match, since `ModelUnavailableError` **is a** kind of `Exception`. That reasoning is correct for **return values**, but **parameters work in reverse**, a property called **contravariance**.

The reasoning for the reversal: a slot that promises "I might pass anything" cannot be safely filled by a function that only handles a narrow type. If something put a `ValueError` into a slot that accepts any `Exception`, a handler expecting `ModelUnavailableError` would break. So for parameters, a function is only safely assignable if it accepts **the same type or a broader one**, never a narrower one.

- Slot wants a function accepting `Exception`.
- Function accepting `Exception` → fine (same).
- Function accepting `BaseException` (broader) → fine.
- Function accepting `ModelUnavailableError` (narrower) → type error.

An analogy: the slot is a job posting that says "must repair any vehicle." A mechanic who only repairs one specific car cannot take it, the job might hand them anything. A mechanic who repairs any vehicle qualifies. The job demands breadth; a narrow specialist does not satisfy it.


## Why it runs fine anyway, and the fixes

At **runtime** none of this matters. FastAPI looks up the raised exception's type in the dict, finds the matching handler, and passes exactly that exception type, which is what the handler expects. It works. The error is purely Pyright doing static analysis, pointing out that the signature is narrower than the slot's contract. The human knows FastAPI's key-matching guarantees safety; the type checker cannot see that guarantee.

Two clean fixes:

- **Widen the annotation, narrow inside.** Annotate `exc: Exception` (matching the slot), and if specific attributes are needed, narrow inside with an `isinstance` check or `assert`, which tells the checker the concrete type from that point on.
- **Accept the approximation.** FastAPI itself types this loosely and the runtime is provably correct, so annotating the specific type and silencing the checker on that line is also defensible.

This project sidesteps the issue differently: a **single handler typed against the base** `LanguagePredictionError`. Because it takes the base type, it matches the slot naturally and reads cleanly, and by inheritance it catches every subtype.


## Handler resolution by inheritance (polymorphism)

When an exception is raised, FastAPI looks for the most specific registered handler:

- A handler registered for a base class catches all its subclasses.
- If a handler is also registered for a specific subclass, the specific one wins for that subclass, and the base handler catches the rest.
- Most specific match wins.

This is the same idea as method resolution in polymorphism, and it is what makes the single base handler work: registered on `LanguagePredictionError`, it catches `ModelUnavailableError`, `PredictionFailedError`, and any future subtype, unless a more specific handler is added.


## The base-handler design

Because every domain exception carries its full taxonomy entry (`status_code`, `error_code`, `message`, `doc_url`) and builds the same response shape, a single handler on the base replaces one-per-type:

```python
async def language_prediction_error_handler(
    request: Request, exc: LanguagePredictionError
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            doc_url=exc.doc_url,
        ).model_dump(),
    )
```

- **One handler instead of several.** The duplication across near-identical handlers collapses into one.
- **The status code lives on the exception** (a class attribute per subclass), so each exception fully owns its taxonomy entry and the handler only reads it.
- **No contravariance complaint**, since the handler takes the base type.
- **Adding a new error type** is just a new subclass with its four values, no new handler.

The tradeoff: a single handler cannot run different logic per type (for example, extra logging for one type only). If that is ever needed, register a more specific handler for that one type and let the base handler catch the rest. For a project where all domain errors are handled identically except for their values, the single base handler is the cleaner choice.


## Why the base exception calls super().__init__(message)

`LanguagePredictionError` inherits from Python's built-in `Exception`. Calling `super().__init__(message)` runs `Exception.__init__`, which stores the message in the exception's `args` tuple. That is what Python uses to **display or stringify** the exception.

- Without it, `str(exc)` is empty, and tracebacks or log lines show the class name with no message.
- With it, `str(exc)` and tracebacks show a meaningful message.

So this is not about the custom `error_code`/`doc_url` fields (those serve the HTTP response). It is about making the exception behave like a proper Python exception in logs, tracebacks, and debugging, the Python-level representation, which is a separate audience from the HTTP client.


## A subtlety specific to HTTPException

FastAPI has its own `HTTPException` (detail can be any JSON-able data) and Starlette has its own (detail is a string only). If a handler is ever registered for `HTTPException`, it must be registered for **Starlette's** version, even though FastAPI's is the one raised in app code, otherwise internally-raised Starlette HTTPExceptions are not caught. This does not affect handlers for `RequestValidationError` or custom domain exceptions, which have no dual-class issue.
