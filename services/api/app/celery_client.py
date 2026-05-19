import os

from celery import Celery

REDIS_URL = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")

celery = Celery("docpilot-api", broker=REDIS_URL, backend=REDIS_URL)
