import logging
import os
from hatchet_sdk import ClientConfig, Hatchet

# Initialize Hatchet client
hatchet = Hatchet(
    debug=True,
    config=ClientConfig(
        token=os.getenv("HATCHET_CLIENT_TOKEN"),
        logger=logging.getLogger("auto-crop-ml"),
    ),

)