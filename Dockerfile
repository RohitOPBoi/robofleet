# Stage 1: Build Frontend Assets
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime
FROM python:3.12-slim AS runner
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast, reliable dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency specifications
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -e .

# Copy application source code
COPY backend/ ./backend/
COPY rules/ ./rules/
COPY scenarios/ ./scenarios/
COPY runs/ ./runs/
COPY examples/ ./examples/

# Copy built frontend static bundle from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose HTTP & WebSocket Command Centre Port
EXPOSE 8000

ENV ROBOFLEET_HOST=0.0.0.0
ENV ROBOFLEET_PORT=8000
ENV PYTHONUNBUFFERED=1

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" || exit 1

ENTRYPOINT ["python", "-m", "robofleet.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
