FROM python:3.13-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev

COPY src/ ./src/

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "python", "-m", "app.main"]
