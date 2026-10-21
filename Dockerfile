FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# curl is used by the container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first to leverage Docker layer caching
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[postgres]"

# Migrations run inside the container (`alembic upgrade head`, see docker-compose.yml)
COPY alembic.ini ./
COPY alembic ./alembic

RUN useradd --create-home --uid 1000 app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://localhost:8000/health || exit 1

# CMD (not ENTRYPOINT) so `docker run <image> <command>` / compose `command:` replace it.
# Behind a reverse proxy, set FORWARDED_ALLOW_IPS to the proxy's IP/CIDR so the
# real client IP (X-Forwarded-For) is used for rate limiting.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
