FROM ghcr.io/trineracz/orezy-backend-base AS base

# Copy source code
COPY app /src/app/
COPY models /src/models/

# Create a non-root user
RUN useradd -m -u 1000 appuser
RUN mkdir -p /upload_data && chown -R appuser:appuser /upload_data
USER appuser
