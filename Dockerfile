FROM trinera/smart-crop-base:1.0.1-rc AS base

# Copy source code
COPY app /src/app/
COPY models /src/models/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create a non-root user
RUN useradd -m -u 1000 appuser
ENTRYPOINT ["/entrypoint.sh"]
