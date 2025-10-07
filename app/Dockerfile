FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential python3-opencv \
 && rm -rf /var/lib/apt/lists/*

# Copy the project into the image
COPY app /src/app/
COPY uv.lock* /src/
COPY pyproject.toml /src/


# Sync the project into a new environment
WORKDIR /src
RUN uv sync --locked

# Create a non-root user
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 8000

