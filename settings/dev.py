from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += ["django_extensions"]  # noqa: F405

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = []

# ── Celery — run tasks synchronously in-process (no queue/worker needed) ──────
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True  # propagate exceptions instead of swallowing

# ── shell_plus — print SQL for all Django ORM queries ─────────────────────────
SHELL_PLUS_PRINT_SQL = True
SHELL_PLUS_SQLPARSE_FORMAT = {
    "reindent": True,
    "keyword_case": "upper",
}

# ── Email — print to console ──────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Logging — verbose output for all CRM components ──────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "core": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "integrations": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
