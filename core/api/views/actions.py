from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import log_action


class PersonActionView(APIView):
    def post(self, request, person_id):
        action_type = request.data.get("action_type")
        note = request.data.get("note", "")
        channel = request.data.get("channel", "")

        if not action_type:
            return Response({"error": "action_type is required"}, status=status.HTTP_400_BAD_REQUEST)

        action_id = log_action(person_id, action_type, note, channel)
        return Response({"action_id": action_id, "person_id": person_id}, status=status.HTTP_201_CREATED)


class LeadActionView(APIView):
    def post(self, request, person_id):
        action_type = request.data.get("action_type")
        note = request.data.get("note", "")
        channel = request.data.get("channel", "")

        if not action_type:
            return Response({"error": "action_type is required"}, status=status.HTTP_400_BAD_REQUEST)

        action_id = log_action(person_id, action_type, note, channel)
        return Response({"action_id": action_id, "person_id": person_id}, status=status.HTTP_201_CREATED)
