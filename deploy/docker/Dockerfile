# ---------- сборка фронтенда ----------
FROM node:22-alpine AS frontend
WORKDIR /src/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ---------- среда выполнения ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Servatory" \
      org.opencontainers.image.version="0.2.0-beta" \
      org.opencontainers.image.licenses="Apache-2.0"

WORKDIR /app
COPY backend/ /app/
RUN pip install --no-cache-dir .
COPY --from=frontend /src/frontend/dist /app/static

RUN useradd --system --uid 10001 --home /data servatory \
 && mkdir -p /data /backups && chown -R servatory:root /data /backups
USER servatory

ENV SERVATORY_DATA=/data \
    SERVATORY_PORT=8090

EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${SERVATORY_PORT}/health" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "app.cli"]
