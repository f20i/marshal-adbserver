FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    git \
    curl \
    adb \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv && \
    mv /root/.local/bin/uvx /usr/local/bin/uvx

WORKDIR /app

COPY . .

RUN chmod +x start.sh

WORKDIR /app/app

RUN uv sync --no-cache

EXPOSE 8000 5037

ENTRYPOINT ["/app/start.sh"]