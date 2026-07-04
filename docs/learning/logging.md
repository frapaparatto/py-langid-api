# Logging


## Why logging (and why not `print`)

Logging is how a program tells the story of what it did, so that behavior can be understood **after the fact**. Once an app runs in production it is a **black box**: no debugger, no live inspection, only the signals it emits. Those signals are the logs.

`print` produces a bare string with no **level**, no **structure**, and no **control** over where it goes. Logging adds those three things, and they are what make logs useful rather than just visible.


## Structured logging: logs are data

Two ways to think about a log entry:

- **Unstructured**: a human sentence. Readable by eye, but to a machine it is an opaque string. To answer a question ("show every request that failed") you must parse sentences with regex.
- **Structured**: a set of key-value fields, rendered as JSON. A machine can **query and filter** by any field.

The principle: **logs are data.** They exist to be consumed by something else (a query, a filter, an aggregator), and that consumption needs fields, not prose. This drives everything else: if logs are data, each entry needs a stable identity and typed fields, which is why a log call is written as an **event name plus key-value data**, not a sentence:

```python
log.info("Model loaded successfully")               # a sentence: unqueryable
log.info("model_loaded", path=settings.model_path)  # an event + data: queryable
```

You are not losing the message. You are splitting it into **what happened** (the stable event name you filter on) and **the specifics of this occurrence** (the data). The rule that follows: the first argument is a short, stable, snake_case event name; everything variable is a keyword argument.

The two limitations of unstructured logging that this solves:
1. Plain text cannot be reliably queried, only regex-matched.
2. Plain text carries no per-request identity, so in a concurrent system, reconstructing one request's activity means correlating by timestamp, which is fragile. Attaching a stable identifier to each request (below) fixes this.


## Log levels: severity as a filter

Every entry has a **level**, in ascending severity:

- **`DEBUG`**: detailed diagnostic detail useful only while actively debugging (for example, the input to a function, an intermediate value).
- **`INFO`**: normal, expected events worth recording (model loaded, request completed).
- **`WARNING`**: something unexpected but survivable; the app continues in a meaningful way.
- **`ERROR`**: an operation failed and could not complete.
- **`CRITICAL`**: the app itself may be unable to continue (rare).

A **threshold** is set once; only entries at or above it are emitted. This controls verbosity without touching code: run at `DEBUG` while developing, `INFO` or higher in production, by changing one config value.

The principle that decides *which* level an event gets: **severity is contextual, not a property of the event type.** The same event means different things in different apps. "Model failed to load" is an `ERROR` for an API whose whole job is the model (a core capability is dead), even though the process survives. The level answers "how bad is this *for this app*."

A second principle for errors specifically: **client fault vs server fault.** A client sending bad input (a 4xx) is expected operation handled correctly, so it is a `WARNING`. A server-side failure (a 5xx) is the app's own problem, so it is an `ERROR`. The level encodes *whose fault it is*.


## Two libraries, two jobs: the production pattern

Logging in this project is built from two libraries with a clean division of labor. The principle is **separation of concerns**: one library structures, the other delivers.

- The **standard library** owns delivery: the logger hierarchy, where output goes (handlers), the threshold, the routing of messages. It is the mature, universal plumbing the whole Python ecosystem already uses.
- **structlog** owns structuring: turning a log call into an enriched, structured event and rendering it.

The value of pairing them: structlog gives the data-first developer experience, and the standard library gives battle-tested delivery *and* a single consistent stream. Because third-party libraries log through the standard library, routing structlog's output through it too means every log in the app, yours and your dependencies', ends up in one place, formatted consistently.

### The hierarchy and propagation (the delivery model)

Loggers form a **tree by name**, with the unnamed **root** at the top. When a message is logged, it does not stop at the logger that emitted it: it **propagates upward** to each ancestor's handlers, up to root. This is a centralizing mechanism: attach the handlers **once, at root**, and every logger funnels its output there without being configured individually. Configuration is centralized at root; the log *calls* stay distributed across the modules where events happen.

(One consequence: adding handlers at both a child and root logs the same message twice. Handlers belong in one place.)

### The setup, as the concrete example

```python
def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # structlog produces the final line, so the stdlib handler must not
    # add its own formatting: %(message)s passes the line through untouched.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Remove existing handlers so re-calling setup is idempotent: calling it
    # twice leaves one set of handlers, not duplicates.
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.set_exc_info,
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

Two things this makes concrete. The **handler** is the stdlib side (where output goes); the **processors** are the structlog side (how the event is built). And the **factory** (`LoggerFactory`) is the seam that hands structlog's finished output to the standard library for delivery. Setup runs **once at startup**; getting a logger anywhere afterward reuses this global configuration.

### The pipeline (the structuring model)

structlog processes each log call through a **pipeline**: the call becomes an **event dict**, which flows through an ordered chain of **processors**, each doing one small job, and ends at a **renderer** that turns the dict into the final output. This is the "small composable steps" philosophy: each stage receives the dict, does one thing, passes it on. Walking the project's chain:

- `merge_contextvars`: merges the per-request bound context (the request ID) into this call's event dict, so ambient context rides on every log.
- `add_log_level`: records the call's level as a field in the output.
- `TimeStamper(fmt="iso")`: adds a timestamp. ISO format sorts correctly as a plain string, so string order equals time order.
- `set_exc_info`: if a log is emitted inside an active exception, flags that exception on the event.
- `format_exc_info`: renders the flagged exception's traceback into the event as data.
- the final processor: the **renderer**, the single point in the pipeline where the accumulated dict becomes the final output string.

Two distinctions the chain makes concrete:

- **Recording the level vs filtering on it.** `add_log_level` writes the level *into the output as a field*. The threshold set on the logger *decides whether the call is emitted at all*. Different jobs: the call carries a level (you call `log.info` or `log.error`), one processor records it, the threshold filters on it.
- **The two-phase flow.** structlog runs the *entire* pipeline first, producing a finished line, and *only then* hands it to the standard library, which propagates it up to root and out. Enrichment happens entirely before delivery. structlog's output is the standard library's input.

### The exception processors (capture then render)

The two exception steps mirror a general principle, separate **capture** from **presentation**: one step flags the active exception on the event, the next renders its traceback into the event as data. The reason this matters for logging errors well: the *rendered traceback* is what carries the diagnostic value. This is also why an exception must never be formatted into the message by hand (`f"error: {e}"`), that bakes it into unqueryable text and discards the traceback. Passing the exception through the pipeline keeps it as structured data.


## Per-request identity and the async problem

The most important thing structured logging buys an API is **correlation**: seeing the whole story of one request across every component it touched. The mechanism is **context binding**.

### The principle: bind once, inherit everywhere

When a request arrives, a request ID is **bound to the logging context** once. From then on, every log call during that request, in the route, the service, the error handler, automatically carries that ID, without it being passed as a parameter. The ID travels **implicitly** through the context. That implicitness is the point: threading an ID through every call by hand would be unbearable, and the payoff is that filtering by one ID reconstructs the entire request.

This is distinct from propagation. Propagation is about *where output goes* (climbing to ancestor handlers). Binding is about *what data a log carries* (fields that accumulate on the context).

### The async isolation problem

The hard question: where does the bound ID live so that **concurrent requests do not corrupt each other**?

- The old answer, **thread-local storage**, works when one request maps to one thread: each thread's context is naturally isolated. Synchronous servers work this way.
- It **breaks under async**, because many requests share **one thread**, interleaved by the event loop. Request A binds its ID, hits an `await`, yields; on the same thread request B binds its ID, overwriting the shared slot; A resumes and reads B's ID. The IDs bleed.

The image that captures it: thread-locals are **one shared screen** showing a single ID. When A pauses and B arrives, B overwrites the screen, so A wakes to the wrong ID. The fix is not to freeze the value, it is to give **each request its own screen**.

The fix is **contextvars**: storage scoped to the **execution context**, which in async means **per-task**, not per-thread. Each task carries its own isolated context even while sharing a thread, so no bleed.

The clarifying model: two concurrent requests to the same endpoint are the **same coroutine function** (the code, the blueprint) run as **two separate tasks** (the executions). Exactly like two instances of a class share methods but hold separate instance data, two tasks share the function but hold separate context. The logger is shared; the bound context riding along with each call is per-task. This is why an async API must bind context with contextvars, not thread-locals.


## The request lifecycle: middleware

Per-request logging lives in **middleware**: code that wraps every request, running **before** the route (on the way in) and **after** it (on the way out). It is the one place to establish per-request identity and log the request boundary, the same centralizing instinct as global exception handlers, applied to requests.

The middleware receives a function (conventionally `call_next`) that represents **the rest of the chain**: inner middleware plus routing to the correct route and running it. Awaiting it hands the request downstream and returns the response.

```python
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    log = structlog.get_logger()

    request_id = str(uuid.uuid4())
    bind_contextvars(request_id=request_id)      # bind once, on the way in
    start_time = time.perf_counter()
    log.debug("request_started", method=request.method, path=request.url.path)

    try:
        response = await call_next(request)      # the route runs here
    except Exception:
        # unanticipated failure: log with traceback, then re-raise so the
        # registered handlers own the response. Do not swallow.
        log.exception("request_failed", method=request.method, path=request.url.path)
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
        clear_contextvars()                      # always clear, so it does not leak
```

The seam is `await call_next`: everything before it runs on the way in, everything after runs on the way out. The response does not exist until the route builds it, so the request's own fields (method, path) are available on the way in, but the outcome (status) only on the way out. The middleware is `async` because it must `await` the downstream chain; because it awaits, other requests interleave on the same thread while it is paused, which is exactly why per-request context must be task-isolated.

Two principles the structure encodes:
1. **Re-raise, do not swallow.** The middleware observes and logs; it does not own the response for errors. The handlers do.
2. **Clear the context every time** (in `finally`). Bound context must be cleared after each request, success or failure, or it bleeds into the next request on the reused task.

Note the request ID is bound, not passed: because `merge_contextvars` is in the pipeline, the ID appears on every log automatically, so the log calls above do not pass `request_id`.

### One log per responded request

A request that produced a response, of *any* status, has **completed its lifecycle**. So a 422 is logged as a completed request with `status=422`, not as a failure: "completed" means the lifecycle finished and produced a response, and the `status` field carries whether the outcome was good or bad. This mirrors real access logs: one uniform line per request, sliced by status code. The genuinely different case, a failure with *no* proper response (an unhandled exception), is the real anomaly and gets its own event.


## Logging errors well: the chain to the root cause

Two ways to log a failure, chosen by one question: **does a live exception's traceback carry diagnostic value that would otherwise be lost?**

- A **known, understood condition** (a value is absent, a file simply is not there): the data tells the whole story, so log it at the right level with descriptive fields. No traceback needed.
- An **unanticipated failure** wrapping an unknown cause: the traceback *is* the diagnostic value, so capture it with `log.exception`, which renders the exception's traceback into the event.

This connects to **exception chaining**. When one exception is raised deliberately from another, `raise DomainError() from original`, the original is preserved on the new exception's `__cause__`. It is the link in the chain: the clean domain error is what the architecture raises, while the *real* underlying failure (for example, an unexpected error from a library deep in the call) is kept on `__cause__` rather than lost. Rendering the traceback walks that chain, so the log shows both the domain error and its true root cause.

The handler that uses this, as the concrete example:

```python
if isinstance(exc, PredictionFailedError):
    # wraps an unknown underlying cause (exc.__cause__): capture the traceback
    log.exception("prediction_error", error_code=exc.error_code, status=exc.status_code)
else:
    # known condition (model not loaded): the data is enough
    log.error("prediction_error", error_code=exc.error_code, status=exc.status_code)
```

The principle: preserve the cause when you raise (`from`), and capture it when you log (`log.exception`). Doing one without the other wastes the effort, chaining the cause but never logging it means the preserved root cause is never seen.


## The recurring principle

One idea threads through all of the above: **centralize configuration, distribute the calls, and keep each log a piece of structured data.** Configuration (the pipeline, the handlers, the threshold) is set up once. The log calls happen at the site of each event, where the relevant context is naturally at hand. And each call is an event name plus data, so the whole stream stays queryable. Everything else, propagation, the pipeline, contextvars, middleware, is machinery in service of those three things.
