FROM python:3.14-slim

RUN pip install --no-cache-dir uv
WORKDIR /app
COPY . .
RUN uv sync --frozen

CMD ["uv", "run", "streamlit", "run", "src/agt/ui/app.py", "--server.port=8501"]
