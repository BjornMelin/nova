# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/docker/library/python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.10.9 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY packages/nova_file_api/pyproject.toml packages/nova_file_api/README.md ./packages/nova_file_api/
COPY packages/nova_runtime_support/pyproject.toml packages/nova_runtime_support/README.md ./packages/nova_runtime_support/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-file-api \
      --no-install-package nova-file-api \
      --no-install-package nova-runtime-support

COPY packages/nova_file_api ./packages/nova_file_api
COPY packages/nova_runtime_support ./packages/nova_runtime_support

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-file-api \
      --no-editable

FROM public.ecr.aws/docker/library/python:3.12-slim

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

USER appuser

EXPOSE 8050
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import sys,urllib.request;urllib.request.urlopen('http://127.0.0.1:8050/v1/health/live', timeout=3);sys.exit(0)"

CMD ["uvicorn", "nova_file_api.main:app", "--host", "0.0.0.0", "--port", "8050", "--proxy-headers", "--forwarded-allow-ips=*"]
