FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev --no-install-project

COPY src/ src/
COPY main.py ./
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "python", "main.py"]
