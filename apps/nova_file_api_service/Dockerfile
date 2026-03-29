# syntax=docker/dockerfile:1.7
ARG BASE_IMAGE=public.ecr.aws/docker/library/python:3.13-slim@sha256:7d8999b140f22939451e00b79c0fd86f13d0bc0577b369f8212fce063101fb2a
FROM ${BASE_IMAGE} AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
# Copy workspace metadata so uv can resolve nova_dash_bridge during build; it is excluded from installation below.
COPY packages/nova_dash_bridge/pyproject.toml packages/nova_dash_bridge/README.md ./packages/nova_dash_bridge/
COPY packages/nova_file_api/pyproject.toml packages/nova_file_api/README.md ./packages/nova_file_api/
COPY packages/nova_runtime_support/pyproject.toml packages/nova_runtime_support/README.md ./packages/nova_runtime_support/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-file-api \
      # Keep nova_dash_bridge out of the image; only its metadata is needed for dependency resolution.
      --no-install-package nova-dash-bridge \
      --no-install-package nova-file-api \
      --no-install-package nova-runtime-support

COPY packages/nova_file_api ./packages/nova_file_api
COPY packages/nova_runtime_support ./packages/nova_runtime_support

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-file-api \
      # Keep nova_dash_bridge out of the image; only its metadata is needed for dependency resolution.
      --no-install-package nova-dash-bridge \
      --no-editable

FROM ${BASE_IMAGE}

ENV PATH="/app/.venv/bin:$PATH" \
    AWS_LWA_PORT=8050 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

# Pin the stable adapter release for the production Lambda Web Adapter path.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:v0.9.1 /lambda-adapter /opt/extensions/lambda-adapter

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

USER appuser

EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import sys,urllib.request;urllib.request.urlopen('http://127.0.0.1:8050/v1/health/live', timeout=3);sys.exit(0)"

CMD ["uvicorn", "nova_file_api.main:app", "--host", "0.0.0.0", "--port", "8050", "--proxy-headers", "--forwarded-allow-ips=*"]
