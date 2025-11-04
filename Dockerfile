FROM ghcr.io/astral-sh/uv:python3.13-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential python3-opencv \
 && rm -rf /var/lib/apt/lists/*

# setup CA trust
RUN curl -fsSL https://curl.se/ca/cacert.pem -o /usr/local/share/ca-certificates/cacert.pem \
 && update-ca-certificates

COPY app /src/app/
COPY models /src/models/
COPY uv.lock* /src/
COPY pyproject.toml /src/

WORKDIR /src
# Sync the project into a new environment
# TODO uncoment after push test
RUN uv sync --locked

# Create a non-root user
RUN useradd -m -u 1000 appuser
RUN mkdir -p /upload_data && chown -R appuser:appuser /upload_data
USER appuser
