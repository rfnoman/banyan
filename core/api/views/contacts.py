import json
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import (
    create_or_merge_person,
    create_or_merge_business,
    link_person_to_business,
    get_person_with_connections,
    get_business_by_id,
)


class ContactCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    """
    External-facing API for creating contacts (people and/or businesses).

    POST /api/contacts/

    Supports three modes via the `type` field:
      - "person"   — create/merge a person node
      - "business" — create/merge a business node
      - "both"     — create both and link with WORKS_AT relationship

    Person fields:   name*, email*, title, linkedin_url, location, source, score
    Business fields: name*, industry, size, website, location

    * = required for that type
    """

    def post(self, request):
        data = request.data
        contact_type = data.get("type", "").lower()

        if contact_type not in ("person", "business", "both"):
            return Response(
                {"error": "type is required and must be 'person', 'business', or 'both'"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if contact_type in ("person", "both"):
            person_data = data.get("person", data) if contact_type == "both" else data
            if not person_data.get("email") or not person_data.get("name"):
                return Response(
                    {"error": "name and email are required for person"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if contact_type in ("business", "both"):
            business_data = data.get("business", data) if contact_type == "both" else data
            if not business_data.get("name"):
                return Response(
                    {"error": "name is required for business"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        result = {}

        if contact_type == "person":
            person_id = create_or_merge_person(data)
            person = get_person_with_connections(person_id)
            result = _serialize_person(person)

        elif contact_type == "business":
            business_id = create_or_merge_business(data)
            business = get_business_by_id(business_id)
            result = business

        elif contact_type == "both":
            person_data = data.get("person", {})
            business_data = data.get("business", {})

            person_id = create_or_merge_person(person_data)
            business_id = create_or_merge_business(business_data)
            link_person_to_business(person_id, business_id)

            person = get_person_with_connections(person_id)
            business = get_business_by_id(business_id)
            result = {
                "person": _serialize_person(person),
                "business": business,
            }

        return Response(result, status=status.HTTP_201_CREATED)


def _serialize_person(p: dict) -> dict:
    tags = p.get("ai_tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    return {**p, "ai_tags": tags or []}
