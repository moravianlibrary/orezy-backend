import logging
import os
from hatchet_sdk import ClientConfig, Hatchet

logging.basicConfig(level=logging.INFO)
root_logger = logging.getLogger()

# Initialize Hatchet client
hatchet = Hatchet(
    debug=True,
    config=ClientConfig(
        token=os.getenv("HATCHET_CLIENT_TOKEN"),
        logger=root_logger,
    ),
)
