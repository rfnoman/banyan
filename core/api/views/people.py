import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import (
    get_all_people,
    create_or_merge_person,
    get_person_with_connections,
)


def _serialize_person(p: dict) -> dict:
    tags = p.get("ai_tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    return {**p, "ai_tags": tags or []}


class PeopleListView(APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        people = get_all_people(limit=limit, offset=offset)
        return Response([_serialize_person(p) for p in people])

    def post(self, request):
        data = request.data
        if not data.get("email") or not data.get("name"):
            return Response({"error": "name and email are required"}, status=status.HTTP_400_BAD_REQUEST)
        person_id = create_or_merge_person(data)
        person = get_person_with_connections(person_id)
        return Response(_serialize_person(person), status=status.HTTP_201_CREATED)


class PersonDetailView(APIView):
    def get(self, request, person_id):
        person = get_person_with_connections(person_id)
        if not person:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_serialize_person(person))
