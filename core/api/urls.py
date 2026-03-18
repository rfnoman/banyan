from django.urls import path
from core.api.views.people import PeopleListView, PersonDetailView
from core.api.views.businesses import BusinessListView, BusinessDetailView
from core.api.views.leads import LeadListView, LeadStageView
from core.api.views.graph import GraphSnapshotView, GraphEdgeView
from core.api.views.analytics import AnalyticsSummaryView, AnalyticsEventsView
from core.api.views.actions import PersonActionView, LeadActionView
from core.api.views.ai_tags import AITagsView, AITagsRetagView
from core.api.views.contacts import ContactCreateView

urlpatterns = [
    # Contacts (external app integration)
    path("contacts/", ContactCreateView.as_view(), name="contact-create"),

    # People

    path("people/", PeopleListView.as_view(), name="people-list"),
    path("people/<str:person_id>/", PersonDetailView.as_view(), name="person-detail"),
    path("people/<str:person_id>/actions/", PersonActionView.as_view(), name="person-actions"),
    path("people/<str:person_id>/ai-tags/", AITagsView.as_view(), name="person-ai-tags"),
    path("people/<str:person_id>/ai-tags/retag/", AITagsRetagView.as_view(), name="person-ai-retag"),

    # Businesses
    path("businesses/", BusinessListView.as_view(), name="business-list"),
    path("businesses/<str:business_id>/", BusinessDetailView.as_view(), name="business-detail"),

    # Leads
    path("leads/", LeadListView.as_view(), name="lead-list"),
    path("leads/<str:person_id>/stage/", LeadStageView.as_view(), name="lead-stage"),
    path("leads/<str:person_id>/actions/", LeadActionView.as_view(), name="lead-actions"),

    # Graph
    path("graph/snapshot/", GraphSnapshotView.as_view(), name="graph-snapshot"),
    path("graph/edge/", GraphEdgeView.as_view(), name="graph-edge"),

    # Analytics
    path("analytics/summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("analytics/events/", AnalyticsEventsView.as_view(), name="analytics-events"),
]
