# BASPAR CMMS — single-service image (API + static frontend).
# Multi-server scale-out: run multiple replicas behind a load balancer;
# swap the event bus for Redis Pub/Sub (see docs/architecture.md §Real-Time).
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY database ./database
COPY frontend ./frontend
COPY scripts ./scripts

# Storage lives on a volume in production (docker-compose).
RUN mkdir -p storage/db storage/uploads storage/backups

EXPOSE 8000

# Migration + seed run automatically on boot (both are idempotent).
CMD ["sh", "-c", "python scripts/migrate.py && python scripts/seed.py && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
