import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.auth import ExternalAppKeyAuthentication
from .events import on_contact_created, on_contact_updated

logger = logging.getLogger(__name__)

EVENT_HANDLERS = {
    "contact_created": on_contact_created,
    "contact_updated": on_contact_updated,
}


class ExternalContactWebhookView(APIView):
    authentication_classes = [ExternalAppKeyAuthentication]
    permission_classes = []

    def post(self, request):
        app = getattr(request, "external_app", None)
        if not app:
            return Response(
                {"error": "API key required"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        source_app = app.name
        event_type = request.data.get("event_type")

        if event_type not in EVENT_HANDLERS:
            return Response(
                {"error": f"Invalid event_type. Must be one of: {list(EVENT_HANDLERS.keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        handler = EVENT_HANDLERS[event_type]
        contacts = request.data.get("contacts", [])

        # Support single-contact mode (fields at top level)
        if not contacts and "name" in request.data and "email" in request.data:
            contacts = [request.data]

        if not contacts:
            return Response(
                {"error": "No contacts provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        processed = 0
        errors = 0
        for contact in contacts:
            try:
                handler(contact, source_app)
                processed += 1
            except Exception as exc:
                logger.warning("Failed to process %s contact: %s", source_app, exc)
                errors += 1

        logger.info(
            "External webhook: app=%s event=%s processed=%d errors=%d",
            source_app, event_type, processed, errors,
        )
        return Response(
            {"processed": processed, "errors": errors},
            status=status.HTTP_201_CREATED,
        )
