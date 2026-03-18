from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        from core.graph.schema import apply_schema
        try:
            apply_schema()
        except Exception:
            pass  # Neo4j may not be up at import time

        # Register Neo4j sync signals (PostgreSQL → Neo4j for graph visualization)
        import core.graph.sync  # noqa: F401
