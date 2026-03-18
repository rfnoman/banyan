"""
Base Django settings shared across all environments.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-change-me-in-production")

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

DJANGO_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "channels",
]

LOCAL_APPS = [
    "core",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Django Unfold Admin
UNFOLD = {
    "SITE_TITLE": "Banyan Tree Admin",
    "SITE_HEADER": "Banyan Tree",
    "SITE_SYMBOL": "hub",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "ENVIRONMENT": "core.admin.environment_callback",
    "DASHBOARD_CALLBACK": "core.admin.dashboard_callback",
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Dashboard",
                "separator": False,
                "collapsible": False,
                "items": [
                    {
                        "title": "Dashboard",
                        "icon": "dashboard",
                        "link": "/admin/",
                    },
                ],
            },
            {
                "title": "CRM Data",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "People",
                        "icon": "person",
                        "link": "/admin/neo4j/people/",
                    },
                    {
                        "title": "Businesses",
                        "icon": "business",
                        "link": "/admin/neo4j/businesses/",
                    },
                    {
                        "title": "Leads",
                        "icon": "leaderboard",
                        "link": "/admin/neo4j/leads/",
                    },
                    {
                        "title": "Sales Pipeline",
                        "icon": "view_kanban",
                        "link": "/admin/neo4j/pipeline/",
                    },
                    {
                        "title": "Products",
                        "icon": "inventory_2",
                        "link": "/admin/neo4j/products/",
                    },
                    {
                        "title": "Contacts",
                        "icon": "contact_mail",
                        "link": "/admin/neo4j/contacts/",
                    },
                    {
                        "title": "Import Contacts",
                        "icon": "upload_file",
                        "link": "/admin/neo4j/imports/",
                    },
                    {
                        "title": "Graph Explorer",
                        "icon": "hub",
                        "link": "/admin/neo4j/graph/",
                    },
                ],
            },
            {
                "title": "Auth & Users",
                "separator": True,
                "collapsible": False,
                "items": [
                    {
                        "title": "Users",
                        "icon": "people",
                        "link": "/admin/auth/user/",
                    },
                    {
                        "title": "Groups",
                        "icon": "group",
                        "link": "/admin/auth/group/",
                    },
                ],
            },
        ],
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "core" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# PostgreSQL — Django auth only
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "graphcrm"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# Neo4j
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

# ClickHouse
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "9000"))
CLICKHOUSE_DB = os.environ.get("CLICKHOUSE_DB", "default")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "")

# RabbitMQ
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Redis
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ROUTES = {
    "core.llm.tasks.*": {"queue": "llm"},
    "core.tasks.*": {"queue": "default"},
}

# Django Channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# Anthropic
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# CRM Products list (used by LLM tagger)
CRM_PRODUCTS = os.environ.get("CRM_PRODUCTS", "ProductA,ProductB,ProductC").split(",")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
