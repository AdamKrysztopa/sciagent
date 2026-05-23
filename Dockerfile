# Stage 1 — Build admin panel
FROM node:20-slim AS admin-panel-builder
WORKDIR /panel
COPY admin-panel/package*.json ./
RUN npm ci
COPY admin-panel/ .
RUN npm run build

# Stage 2 — Python backend
FROM python:3.14-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY . .
COPY --from=admin-panel-builder /panel/dist /app/admin-panel/dist
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["sh", "-c", "/app/.venv/bin/uvicorn agt.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
