# SmartCrop

SmartCrop serves as the backend for the web application Cropilot. It provides automated document processing capabilities that detect page boundaries and correct orientation. The service exposes an API used by the frontend and orchestrates a machine learning pipeline that analyzes uploaded images, identifies page coordinates, and applies rotation correction when needed.


## Application structure

The application is designed as a modular service combining a FastAPI interface, a background task queue, and a set of fine-tuned deep learning models. Image processing tasks are executed asynchronously through a worker system, enabling scalable and efficient handling of large batches of documents while storing metadata and processing results in MongoDB. Application is arranged into following modules:

- **api**: FastAPI routers for integration control and frontend.
- **core**: Contains a finetuned YOLO model for page coordinate detection and a ResNET-based rotation model for skew correction.
- **db**: MongoDB collections defined with Pydantic and related Mongo queries.
- **tasks**: Hatchet task queue and worker. Contains tasks performing the ML pipeline.


# Development

Development cheat sheet:

- `uvx ruff format . && uvx ruff check --fix .`  Format the project and fix linter errors
- `uv run pytest -v` Run tests
