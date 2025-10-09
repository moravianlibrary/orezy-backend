FROM ghcr.io/astral-sh/uv:python3.13-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential python3-opencv \
 && rm -rf /var/lib/apt/lists/*

COPY . /src/
WORKDIR /src
# Sync the project into a new environment
# TODO uncoment after push test
RUN uv sync --locked
