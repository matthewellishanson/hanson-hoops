# backend/Dockerfile
FROM python:3.12-slim

# System deps (handy for numpy/pandas/http)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Better layer caching: install deps first
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy backend code (puts your "app" package at /app/app -> app.main:app)
COPY backend /app

# Env for logs and port
ENV PYTHONUNBUFFERED=1 \
    PORT=8000

# Start FastAPI (bind to $PORT for Render)
# If you add WEB_CONCURRENCY in Render env, gunicorn will use it; else default to 2
CMD ["bash", "-lc", "exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:${PORT} --timeout 120 --workers ${WEB_CONCURRENCY:-2}"]
