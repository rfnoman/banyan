import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status

from core.messaging.publisher import CRMPublisher
from .scraper import ApifyScraper
from .transformer import apify_profile_to_lead_event

logger = logging.getLogger(__name__)


class ApifyWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        product = request.data.get("product", "ProductA")
        dataset_id = request.data.get("items") or request.data.get("defaultDatasetId")
        profiles = request.data.get("profiles", [])

        if dataset_id and not profiles:
            try:
                scraper = ApifyScraper()
                profiles = scraper.fetch_dataset(dataset_id)
            except Exception as exc:
                logger.error("Failed to fetch Apify dataset %s: %s", dataset_id, exc)
                return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        published = 0
        errors = 0
        with CRMPublisher() as pub:
            for profile in profiles:
                try:
                    event = apify_profile_to_lead_event(profile, product)
                    pub.publish_lead(event)
                    published += 1
                except Exception as exc:
                    logger.warning("Failed to process Apify profile: %s", exc)
                    errors += 1

        logger.info("Apify webhook: published=%d errors=%d product=%s", published, errors, product)
        return Response({"published": published, "errors": errors})
