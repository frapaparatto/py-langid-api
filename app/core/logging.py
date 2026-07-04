import structlog
import logging
import sys


def setup_logging(log_level: str = "INFO", log_format: str = "json") -> None:
    """
    Configure application logging once at startup.

    Logs are written as an event stream to stdout, following the 12-factor
    principle that an app should not manage its own log files: it emits a
    structured stream and the execution environment (Docker, the platform,
    or a shell redirect in local dev) decides routing and storage. This
    keeps the app free of file rotation, disk-space, and path concerns.

    structlog builds and renders the structured event; the standard library
    delivers it to stdout. The renderer is chosen by log_format: JSON for
    machine consumption (production), pretty console output for local dev.
    The threshold is set by log_level.
    """
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    # stdout handler with a pass-through formatter: structlog has already
    # produced the final line, so stdlib must not add its own formatting.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))

    # Remove existing handlers so re-calling setup_logging is idempotent
    # (matters in tests / reloads, where the process persists).
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.set_exc_info,
    ]

    if log_format == "json":
        processors = shared_processors + [
            structlog.processors.format_exc_info,  # JSON needs the traceback rendered
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),  # renders exceptions itself
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
