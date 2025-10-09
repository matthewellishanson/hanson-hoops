# backend/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for layer caching
COPY backend/requirements.txt requirements.txt

# ---- Prevent proxy from interfering with pip during build ----
ENV HTTP_PROXY= \
    HTTPS_PROXY= \
    http_proxy= \
    https_proxy= \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=60 \
    PIP_INDEX_URL=https://pypi.org/simple

# Install Python deps (prefer wheels)
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy backend source
COPY backend /app

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

CMD ["bash","-lc","exec gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:${PORT} --timeout 120 --workers ${WEB_CONCURRENCY:-2}"]
