# syntax=docker/dockerfile:1.7
FROM public.ecr.aws/lambda/python:3.13

COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /var/task

COPY pyproject.toml uv.lock README.md ./
COPY packages/nova_file_api/pyproject.toml packages/nova_file_api/README.md ./packages/nova_file_api/
COPY packages/nova_runtime_support/pyproject.toml packages/nova_runtime_support/README.md ./packages/nova_runtime_support/
COPY packages/nova_workflows/pyproject.toml packages/nova_workflows/README.md ./packages/nova_workflows/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-workflows \
      --no-install-package nova-workflows \
      --no-install-package nova-file-api \
      --no-install-package nova-runtime-support

COPY packages/nova_file_api ./packages/nova_file_api
COPY packages/nova_runtime_support ./packages/nova_runtime_support
COPY packages/nova_workflows ./packages/nova_workflows

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
      --frozen \
      --no-default-groups \
      --package nova-workflows \
      --no-editable

ENV PATH="/var/task/.venv/bin:$PATH"
