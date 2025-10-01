# Auto Crop ML

Auto Crop ML processes image scans and outputs crop and rotation instructions to extract individual pages.

## Modules

- **api**: FastAPI routers for integration control and the Auto Crop web app backend.  
    Run with:  
    ```
    uv run --env-file .env fastapi dev
    ```
    Access at [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

- **core**: Contains a finetuned YOLO model for page coordinate detection and a Hough rotation model for skew correction.

- **db**: MongoDB collections defined with Pydantic and related Mongo queries.

- **tasks**: Hatchet task queue and worker.  
    - Start hatchet-lite via `docker-compose` (available at [http://localhost:8888/](http://localhost:8888/)).  
    - Run a Hatchet worker with:  
        ```
        uv run --env-file .env -m app.tasks.worker
        ```

## Development

- Ensure your local `.env` file includes:
    - `MONGODB_URI`
    - `MONGODB_DB`
    - `HATCHET_CLIENT_TOKEN`
- Format the project using:
    ```
    uvx ruff format .
    ```
