"""Standalone background worker: `python -m app.worker`."""

import logging

from .services import pipeline  # noqa: F401  (registers job handlers)
from .services.jobs import worker_loop

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker_loop()
