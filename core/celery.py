import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.dev")

app = Celery("core")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks([
    "core.tasks",
    "core.llm",
])

app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "llm": {"exchange": "llm", "routing_key": "llm"},
}

app.conf.task_default_queue = "default"
