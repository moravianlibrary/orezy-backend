import logging
from app.tasks.hatchet_client import hatchet
from app.tasks.workflows.workflow_mongo import autocrop_workflow, upload_workflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auto-crop-ml")


def main() -> None:
    worker = hatchet.worker(
        "crop-worker", slots=1, workflows=[autocrop_workflow, upload_workflow]
    )
    worker.start()


if __name__ == "__main__":
    main()
