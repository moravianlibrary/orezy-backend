#!/bin/sh
set -e

if [ -n "$RETRAIN_VOLUME_PATH" ]; then
    mkdir -p "$RETRAIN_VOLUME_PATH"
    chown -R appuser:appuser "$RETRAIN_VOLUME_PATH" || true
fi

if [ -n "$MODELS_VOLUME_PATH" ]; then
    mkdir -p "$MODELS_VOLUME_PATH"
    chown -R appuser:appuser "$MODELS_VOLUME_PATH" || true
fi

if [ -n "$SCANS_VOLUME_PATH" ]; then
    mkdir -p "$SCANS_VOLUME_PATH"
    chown -R appuser:appuser "$SCANS_VOLUME_PATH" || true
fi

# Execute the command as the non-root user
exec gosu appuser "$@"