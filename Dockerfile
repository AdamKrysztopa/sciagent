FROM python:3.14-slim

RUN pip install --no-cache-dir uv
WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev

EXPOSE 8080
CMD ["sh", "-c", "/app/.venv/bin/uvicorn agt.api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
