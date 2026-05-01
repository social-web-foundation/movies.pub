# syntax=docker/dockerfile:1.7

# ---- builder: resolve and install deps into /app/.venv ----
FROM python:3.14-slim-bookworm AS builder

# pull the uv binary from Astral's official image (pinned)
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# copy only manifests first so source edits don't bust the dep cache
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---- runtime: small image, just venv + source ----
FROM python:3.14-slim-bookworm AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app main.py ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
