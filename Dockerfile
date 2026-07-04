FROM python:3.12-slim-bookworm

WORKDIR /app

# Instala uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copia dependências e instala
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copia o resto do código
COPY . .

EXPOSE 8000

CMD ["/app/.venv/bin/python", "-m", "server.main"]
