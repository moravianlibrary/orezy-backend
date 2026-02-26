FROM trinera/smart-crop-base:1.0.1-rc AS base

# Copy source code
COPY app /src/app/
COPY models /src/models/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create a non-root user
RUN useradd -m -u 1000 appuser

# create volume dirs at build-time if corresponding env vars are set
RUN /bin/sh -c '\
    if [ -n "$RETRAIN_VOLUME_PATH" ]; then \
        mkdir -p "$RETRAIN_VOLUME_PATH" && chown -R appuser:appuser "$RETRAIN_VOLUME_PATH" || true; \
    fi; \
    if [ -n "$MODELS_VOLUME_PATH" ]; then \
        mkdir -p "$MODELS_VOLUME_PATH" && chown -R appuser:appuser "$MODELS_VOLUME_PATH" || true; \
    fi; \
    if [ -n "$SCANS_VOLUME_PATH" ]; then \
        mkdir -p "$SCANS_VOLUME_PATH" && chown -R appuser:appuser "$SCANS_VOLUME_PATH" || true; \
    fi'

USER appuser

ENV RETRAIN_VOLUME_PATH="${RETRAIN_VOLUME_PATH}"
ENV MODELS_VOLUME_PATH="${MODELS_VOLUME_PATH}"
ENV SCANS_VOLUME_PATH="${SCANS_VOLUME_PATH}"
