# syntax=docker/dockerfile:1.7
# Multi-stage build for AllInclusiveParser web panel.
#
# Stage 1: build the SvelteKit SPA into static assets.
# Stage 2: install Python deps for the parser + FastAPI backend, copy in
#          the SPA, and serve the whole thing on port 8000.

# ---- Stage 1: frontend ---------------------------------------------------
FROM node:20-bookworm-slim AS frontend
WORKDIR /app/webpanel/frontend

COPY webpanel/frontend/package.json webpanel/frontend/package-lock.json* ./
RUN npm ci

COPY webpanel/frontend/ ./
RUN npm run build


# ---- Stage 2: runtime ----------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for cryptg / cryptography wheels that occasionally need them.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libffi-dev \
       libssl-dev \
       ca-certificates \
       curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install parser runtime deps (use the curated requirements.runtime.txt that
# pins to versions that exist on PyPI — see the file for the rationale).
COPY requirements.runtime.txt ./
RUN pip install -r requirements.runtime.txt

# Install the FastAPI backend as a package (the package itself is small,
# but its dependencies are heavy — keep this layer separate for caching).
COPY webpanel/backend/pyproject.toml webpanel/backend/README.md /app/webpanel/backend/
COPY webpanel/backend/app /app/webpanel/backend/app
RUN pip install /app/webpanel/backend

# Now bring in the parser source and supporting files.
COPY src /app/src
COPY config /app/config
COPY main.py automation.py ./
# Channels file is optional in CI; bind-mount in production.
COPY channels.txt ./

# Frontend build output lives next to the backend so PANEL_FRONTEND_DIR works.
COPY --from=frontend /app/webpanel/frontend/build /app/webpanel/frontend/build

ENV PANEL_FRONTEND_DIR=/app/webpanel/frontend/build \
    PANEL_DATA_DIR=/app/webpanel/backend/data \
    PARSER_SESSION_DIR=/app/sessions \
    PARSER_LOG_DIR=/app/logs

# Volumes that should outlive the container.
RUN mkdir -p /app/sessions /app/data /app/logs /app/exports /app/webpanel/backend/data

EXPOSE 8000

# uvicorn directly — gunicorn is overkill for a single-tenant admin panel.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--app-dir", "/app/webpanel/backend"]
