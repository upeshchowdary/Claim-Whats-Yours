# Production backend image. Docker build context is ./backend.
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

# psycopg[binary] normally does not need a compiler, so keep the image minimal.
COPY pyproject.toml ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY data ./data
COPY scripts ./scripts

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

RUN useradd --create-home --uid 1000 appuser && \
    chown --recursive appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=5)" || exit 1

# Migrations must run before the API process serves traffic.
CMD ["sh", "-c", "python -m alembic upgrade head && python scripts/seed_database.py && uvicorn claim_whats_yours.app:app --host 0.0.0.0 --port 8000"]
