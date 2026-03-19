from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
# from integrations.apify.webhook import ApifyWebhookView  # Apify disabled
from integrations.external.webhook import ExternalContactWebhookView
from core.admin_views import (
    BusinessDetailView,
    BusinessListView,
    ContactListView,
    GraphExplorerView,
    GraphSnapshotAPIView,
    ImportLinkedInScrapeAPIView,
    ImportListView,
    LeadListView,
    PeopleListView,
    PersonDetailView,
    PipelineLeadsAPIView,
    PipelineStageUpdateView,
    PipelineView,
    ProductDetailView,
    ProductListView,
)

urlpatterns = [
    # Neo4j admin views (must be before admin/ to avoid being caught by admin catch-all)
    path("admin/neo4j/people/", PeopleListView.as_view(), name="admin-neo4j-people"),
    path("admin/neo4j/people/<str:person_id>/", PersonDetailView.as_view(), name="admin-neo4j-person-detail"),
    path("admin/neo4j/businesses/", BusinessListView.as_view(), name="admin-neo4j-businesses"),
    path("admin/neo4j/businesses/<str:business_id>/", BusinessDetailView.as_view(), name="admin-neo4j-business-detail"),
    path("admin/neo4j/leads/", LeadListView.as_view(), name="admin-neo4j-leads"),
    path("admin/neo4j/products/", ProductListView.as_view(), name="admin-neo4j-products"),
    path("admin/neo4j/products/<str:product_id>/", ProductDetailView.as_view(), name="admin-neo4j-product-detail"),
    path("admin/neo4j/contacts/", ContactListView.as_view(), name="admin-neo4j-contacts"),
    path("admin/neo4j/pipeline/", PipelineView.as_view(), name="admin-neo4j-pipeline"),
    path("admin/neo4j/pipeline/api/leads/", PipelineLeadsAPIView.as_view(), name="admin-neo4j-pipeline-leads"),
    path("admin/neo4j/pipeline/api/stage/", PipelineStageUpdateView.as_view(), name="admin-neo4j-pipeline-stage"),
    path("admin/neo4j/imports/", ImportListView.as_view(), name="admin-neo4j-imports"),
    path("admin/neo4j/imports/api/scrape-linkedin/", ImportLinkedInScrapeAPIView.as_view(), name="admin-neo4j-scrape-linkedin"),
    path("admin/neo4j/graph/", GraphExplorerView.as_view(), name="admin-neo4j-graph"),
    path("admin/neo4j/graph/api/", GraphSnapshotAPIView.as_view(), name="admin-neo4j-graph-api"),
    # Django admin
    path("admin/", admin.site.urls),
    # API auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("core.api.urls")),
    # path("api/apify/webhook/", ApifyWebhookView.as_view(), name="apify-webhook"),  # Apify disabled
    path("api/external/contacts/", ExternalContactWebhookView.as_view(), name="external-contacts-webhook"),
]
