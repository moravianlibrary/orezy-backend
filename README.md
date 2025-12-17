# SmartCrop app

SmartCrop is a web application that extracts page coordinates out of scans. When a new book or other scanned media is uploaded, a machine learning model
predicts the location and angle of pages inside the image. User is then able to review and edit the predictions in a web UI.

## Application structure

The project stack includes Hatchet queue manager, FastAPI, MongoDB, and set of finetuned PyTorch models. Application is arranged into following modules:

- **api**: FastAPI routers for integration control and frontend.

- **core**: Contains a finetuned YOLO model for page coordinate detection and a ResNET-based rotation model for skew correction.

- **db**: MongoDB collections defined with Pydantic and related Mongo queries.

- **tasks**: Hatchet task queue and worker. Contains tasks performing the ML pipeline.

# Deployment

The project is built using uv and package-managed by ruff. Each instance is containerized into Docker containers. This repo offers 2 types of deployment:

## Local

To run your application locally, use docker-compose.hatchet-local.yml. Prerequisites of running PageTrace locally include setting up your MongoDB instance (e.g. on https://www.mongodb.com/products/platform/atlas-database) and creating .env file. Your environment file should have this structure:

.env
```
WEBAPP_TOKEN = Create your Bearer token used in API
MONGODB_URI = Url to your MongoDB instance
MONGODB_PASS = Create your DB password
MONGODB_DB = DB name
ENABLE_TLS = true
SCANS_VOLUME_PATH = Local directory path where new images will be uploaded via API
RETRAIN_VLUME_PATH = Local directory where images marked for retraining will be saved
HATCHET_CLIENT_TLS_STRATEGY = none
HATCHET_CLIENT_TOKEN = Hatchet token. Can be acessed via Hatchet web instance, or created with generate-worker-env.sh
```

Then, run the application in following steps:

- `docker-compose up -f docker-compose.hatchet-local.yml -d` Start required services (Hatchet server, PostgreSQL and RabbitMQ as Hatchet backend)
- `uv run --env-file .env fastapi dev`  Start API locally, Swagger UI will be available at http://127.0.0.1:8000/docs
- `uv run --env-file .env -m app.tasks.worker`  Start worker locally. The UI is available at http://127.0.0.1:8888/

## Production

The production version is stored in docker-compose.yml, and uses 3 environment files in total, which need to be set accordingly:

- *.env*: A password file. Create this file from .env.example, replace with your generated passwords. You will be regularly using WEBAPP_TOKEN variable for communication with API, the rest is internal to the application.
- *.hatchet-user-env*: A Hatchet UI login file. Create it from .hatchet-user-env.example. Use strong passwords, as the access to this UI allows spawning custom tasks.
- *.worker-env*: Contains a JWT token obtained from Hatchet. Generate the file by running `bash generate-worker-env.sh`.

Inside docker compose itself, there are 2 variables which you can update optionally. SCANS_VOLUME_PATH points to volume used for storing uploaded files (via frontend), and RETRAIN_VOLUME_PATH points to volume with saved images used for retraining.

Finally, run the application with:

- `docker-compose up -d` Start all services (Hatchet server, PostgreSQL and RabbitMQ as Hatchet backend, MongoDB, API, and worker). API endpoints will be available at http://127.0.0.1:8000/docs , Hatchet UI at http://127.0.0.1:8888/ ,
and web UI at http://127.0.0.1:1234.


# Development

Development cheat sheet:

- `uvx ruff format . && uvx ruff check --fix .`  Format the project and fix linter errors
- `uv run pytest -v` Run tests
