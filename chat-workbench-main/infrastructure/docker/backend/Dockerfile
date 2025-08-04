FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.13-slim AS builder

# Enable bytecode compilation, to improve cold-start performance.
ENV UV_COMPILE_BYTECODE=1
# Disable installer metadata, to create a deterministic layer.
ENV UV_NO_INSTALLER_METADATA=1
# Enable copy mode to support bind mount caching.
ENV UV_LINK_MODE=copy

# Bundle dependencies into a clean layer
WORKDIR /build
RUN --mount=from=uv,source=/uv,target=/bin/uv \
    --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=backend/pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    uv export --frozen --no-emit-workspace --no-dev -o requirements.txt && \
    uv pip install -r requirements.txt --target /packages

FROM python:3.13-slim

WORKDIR /app

# Copy dependencies from builder stage
COPY --from=builder /packages /app/packages

# Copy application code
COPY backend/app /app/app

ENV PYTHONPATH=/app:/app/packages
ENV AWS_SDK_LOAD_CONFIG=1
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://0.0.0.0:8000/api/health')" || exit 1

CMD ["python", "-m", "app.api.main"]
