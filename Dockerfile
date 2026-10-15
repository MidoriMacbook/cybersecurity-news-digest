# Unified free-hosting deployment: one origin for web UI and FastAPI.
FROM node:22-bookworm-slim AS web
WORKDIR /web
RUN corepack enable
COPY apps/web/package.json apps/web/pnpm-lock.yaml apps/web/pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile
COPY apps/web/ ./
ENV NEXT_PUBLIC_API_URL=""
RUN corepack pnpm build

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home digest
COPY apps/api/app/ ./app/
COPY data/ ./data/
COPY --from=web /web/out/ ./static/
RUN mkdir -p /app/runtime && chown digest:digest /app/runtime
ENV DATABASE_URL=sqlite:////app/runtime/digest.db STATIC_DIR=/app/static DEMO_DATA_DIR=/app/data/demo MODE=mock PORT=8000
USER digest
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
