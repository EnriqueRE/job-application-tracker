# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

# Build the virtualenvs with uv; nothing from this stage but /opt/venv ships.
FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM builder AS builder-dev
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

# Production image: runtime deps only, non-root.
FROM base AS runtime
RUN useradd --create-home --uid 10001 app && install -d -o app -g app /app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app app ./app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Local image: adds dev deps and tests so `make test` runs inside the container.
FROM runtime AS dev
COPY --from=builder-dev /opt/venv /opt/venv
COPY --chown=app:app pyproject.toml ./
COPY --chown=app:app tests ./tests
