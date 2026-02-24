FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY apps ./apps
COPY packages ./packages

RUN uv sync --frozen --no-default-groups --package nova-auth-api-service

EXPOSE 8050

CMD ["uv", "run", "uvicorn", "nova_auth_api_service.main:app", "--host", "0.0.0.0", "--port", "8050"]
