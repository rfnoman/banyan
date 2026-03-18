import os

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group, User
from unfold.admin import ModelAdmin

# ──────────────────────────────────────────────
# Patch: Unfold's _flatten_context crashes on Django 5 + UserAdmin add view
# because a non-dict entry ends up in context.dicts. Make it resilient.
# ──────────────────────────────────────────────
from unfold.templatetags import unfold as _unfold_tags

_original_flatten = _unfold_tags._flatten_context


def _safe_flatten_context(context):
    try:
        return _original_flatten(context)
    except (ValueError, TypeError):
        flat = {}
        for d in context.dicts:
            if isinstance(d, dict):
                flat.update(d)
        return flat


_unfold_tags._flatten_context = _safe_flatten_context


def environment_callback(request):
    """Return current environment label for Unfold header badge."""
    if os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("prod"):
        return "Production"
    return "Development"


def dashboard_callback(request, context):
    """Populate the Unfold dashboard with CRM analytics from Neo4j."""
    from core.db.queries import get_analytics_summary, get_pending_ai_tagging

    try:
        summary = get_analytics_summary()
    except Exception:
        summary = {
            "people": 0,
            "businesses": 0,
            "leads": 0,
            "avg_score": 0,
            "stage_distribution": [],
        }

    try:
        pending_tags = get_pending_ai_tagging(limit=10)
    except Exception:
        pending_tags = []

    # Build stage distribution for display
    stage_rows = []
    for item in summary.get("stage_distribution", []):
        stage_rows.append({
            "stage": item.get("stage", "Unknown"),
            "count": item.get("count", 0),
        })

    # KPI cards
    kpi_cards = [
        {"title": "Total People", "metric": summary.get("people", 0), "icon": "person"},
        {"title": "Total Businesses", "metric": summary.get("businesses", 0), "icon": "business"},
        {"title": "Active Leads", "metric": summary.get("leads", 0), "icon": "leaderboard"},
        {"title": "Avg Lead Score", "metric": summary.get("avg_score", 0), "icon": "speed"},
    ]

    context.update({
        "kpi_cards": kpi_cards,
        "stage_distribution": stage_rows,
        "pending_ai_tags": pending_tags,
        "pending_ai_count": len(pending_tags),
    })
    return context


# ──────────────────────────────────────────────
# Auth models — re-register with Unfold styling
# ──────────────────────────────────────────────

admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    """User admin with Unfold theme."""
    pass


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin, ModelAdmin):
    """Group admin with Unfold theme."""
    pass


from core.models import ExternalApp


@admin.register(ExternalApp)
class ExternalAppAdmin(ModelAdmin):
    list_display = ["name", "display_name", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "display_name"]
    readonly_fields = ["api_key", "created_at"]
