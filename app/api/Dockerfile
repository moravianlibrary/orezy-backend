FROM ghcr.io/trineracz/orezy-backend-base

EXPOSE 8000
WORKDIR /src
# FastAPI dev server via uv
CMD ["uv", "run", "fastapi", "dev", "--host", "0.0.0.0", "--port", "8000"]
