# PageTrace application

This app processes image scans and outputs crop and rotation instructions to extract individual pages.

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
MONGODB_URI = Url to your MongoDB instance
MONGODB_DB = DB name
MONGODB_PW = Create your DB password

ENABLE_TLS = true

SCANS_VOLUME_PATH = Path where new images will be uploaded via API
WEBAPP_TOKEN = Create your Bearer token used in API

HATCHET_CLIENT_TLS_STRATEGY = none
HATCHET_CLIENT_TOKEN = Hatchet token. Can be acessed via Hatchet web instance, or created with generate-worker-env.sh
```

Then, run the application in following steps:

- `docker-compose up -f docker-compose.hatchet-local.yml -d` Start required services (Hatchet server, PostgreSQL and RabbitMQ as Hatchet backend)
- `uv run --env-file .env fastapi dev`  Start API locally, Swagger UI will be available at http://127.0.0.1:8000/docs
- `uv run --env-file .env -m app.tasks.worker`  Start worker locally. The UI is available at http://127.0.0.1:8888/

- `uvx ruff format . && uvx ruff check --fix .`  Format the project and fix linter errors

## Production

The production version is stored in docker-compose.yml. There are 2 prerequisites before running the application. First, go over the environment variables in the docker compose, generate and set secrets (DB passwords, tokens) accordingly. Then, create .hatchet-user-env file which creates login parameters for the Hatchet UI. Use strong passwords, as the access to this UI allows spawning custom tasks. The env file has a following structure: 

.hatchet-user-env
```
ADMIN_EMAIL = Admin email you will use for login
ADMIN_PASSWORD = Setup a password
ADMIN_NAME = Admin
```

Then, run the application in following steps:

- `bash generate-worker-env.sh` Generates a Hatchet API token required for communication between the worker and the server. Saves the token into .worker-env, which will be reused in the docker compose.
- `docker-compose up -d` Start all services (Hatchet server, PostgreSQL and RabbitMQ as Hatchet backend, MongoDB, API, and worker). API endpoints will be available at http://127.0.0.1:8000/docs , Hatchet UI at http://127.0.0.1:8888/ .
