FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    DATABASE_URL="sqlite:////app/nodesh.db" \
    UPLOADS_DIR="/app/uploads" \
    WEB_ORIGIN="*"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/src ./src
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations

RUN pip install --no-cache-dir . && mkdir -p /app/uploads && chmod -R 777 /app/uploads

EXPOSE 7860

CMD ["sh", "-c", "alembic upgrade head && uvicorn nodesh_api.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
