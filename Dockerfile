# Base image tracks a tag, not a digest, unlike the uv copy below.
# Reproducibility is weaker here until this is pinned too.
FROM python:3.13-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /uvx /bin/

WORKDIR /app
ENV UV_NO_DEV=1

COPY pyproject.toml uv.lock /app/
RUN uv sync --locked
COPY . /app

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0"]
