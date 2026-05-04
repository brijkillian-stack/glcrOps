# Unified GLCR Memory + ZDS — Single-stage Docker image
# Architecture:
#   - Reflex backend (FastAPI) listens on localhost:8000
#   - Pre-exported static frontend lives in /app/.web/_static
#   - Caddy listens on $PORT, serves statics and proxies /_event/* to backend
# Deploy: Render Web Service ($7/mo always-on, runtime: docker)

FROM python:3.13-slim

# ---------------------------------------------------------------------------
# System deps:
#   - curl: healthcheck + Caddy install
#   - unzip + ca-certificates: Reflex's bun installer
#   - bash: entrypoint uses `wait -n` (a bash extension)
#   - Caddy: reverse proxy / static file server
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         curl \
         unzip \
         ca-certificates \
         bash \
         debian-keyring \
         debian-archive-keyring \
         apt-transport-https \
         gnupg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
         | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
         > /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends caddy \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# App user.
# ---------------------------------------------------------------------------
RUN useradd -m -u 1000 app

WORKDIR /app

# ---------------------------------------------------------------------------
# Python deps.
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# App code: brijkillian_stack/ (main app), apps/ (GLCR + ZDS), shared/
# ---------------------------------------------------------------------------
COPY brijkillian_stack /app/brijkillian_stack
COPY apps             /app/apps
COPY shared           /app/shared
COPY rxconfig.py      /app/
COPY assets           /app/assets
COPY Caddyfile        /app/Caddyfile
COPY entrypoint.sh    /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ---------------------------------------------------------------------------
# Final ownership sweep.
# ---------------------------------------------------------------------------
RUN chown -R app:app /app

USER app

# ---------------------------------------------------------------------------
# Pre-export the static frontend at build time.
# API_URL is baked into the compiled JS bundle as the WebSocket / RPC origin
# the browser will use to talk to the Reflex backend. Caddy on $PORT proxies
# /_event/* to backend:8000, so the public URL is what the browser must hit.
# ---------------------------------------------------------------------------
ENV API_URL="https://glcrops.onrender.com"
ENV DEPLOY_URL="https://glcrops.onrender.com"
RUN reflex export --frontend-only --no-zip || \
    reflex export --frontend-only || \
    echo "[build] reflex export failed; runtime will compile on first request"

# Render injects $PORT at runtime.
ENV PORT=10000
EXPOSE 10000

# Healthcheck hits Caddy's /health shortcut.
HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=5 \
    CMD curl -fsS "http://localhost:${PORT}/health" || exit 1

CMD ["/app/entrypoint.sh"]
