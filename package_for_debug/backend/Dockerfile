# backend/Dockerfile

FROM python:3.12-slim

# System deps (optional but good for pandas/numpy/http)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Workdir inside the image
WORKDIR /app

# Install deps first (better layer caching)
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy your backend code into /app
# IMPORTANT: this places the "app" package at /app/app so "app.main:app" imports work
COPY backend /app

# Let Render tell us which port to use (defaults to 8000 locally)
ENV PORT=8000

# Start FastAPI
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
