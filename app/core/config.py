from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # env_file tells pydantic-settings to also read a local .env file, not
    # just real environment variables. Precedence: real env vars first,
    # then .env, then the field defaults below. In production no .env
    # exists, the platform injects real env vars and the same class reads
    # them.
    #
    # protected_namespaces=() disables Pydantic's warning about field names
    # starting with "model_". Pydantic reserves that prefix for its own
    # methods (model_dump, model_validate, model_config, ...) and warns on
    # any field that could shadow them. model_path does not actually
    # collide with a real method, so the warning is a false alarm here.
    # Clearing the tuple turns the warning off. The tradeoff: Pydantic will
    # no longer catch a field name that genuinely shadows a model_* method
    # (acceptable for this one-field settings class).
    model_config = SettingsConfigDict(
        env_file=".env",
        protected_namespaces=(),
    )

    # Read from the MODEL_PATH env var (field-to-env matching is
    # case-insensitive). Defaults to ./model.pkl, so the app runs locally
    # with no config set. A missing file at this path is not a config
    # error: it is caught later at model load and surfaced as a 503.
    model_path: str = Field(
        default="./model.pkl",
        description="Filesystem path to the pickled model.",
    )

    # The minimum severity to emit: entries below this level are dropped.
    # Typed as a Literal so an invalid value (a typo like "INFOO") fails
    # validation at startup instead of silently misbehaving.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Minimum severity level to emit (DEBUG, INFO, WARNING, ERROR, CRITICAL).",
    )

    # The stdout rendering format. Typed as a Literal so an unknown value
    # fails at startup rather than falling through to a default branch.
    # "json" for machine consumption, "console" for readable local dev.
    log_format: Literal["json", "console"] = Field(
        default="json",
        description="Log output format on stdout: 'json' for machines, 'console' for readable local dev.",
    )


# Instantiating here runs the load-and-validate once, at import time. If a
# setting is malformed, this raises immediately, so the app fails at
# startup rather than running in a broken state (LBYL by construction, per
# ADR-002).
settings = Settings()
