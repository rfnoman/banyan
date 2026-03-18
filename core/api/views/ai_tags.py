import json
from datetime import datetime, timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import get_ai_tag_history, update_ai_tags, get_person_with_connections
from core.messaging.events import AITagRequestEvent
from core.messaging.publisher import CRMPublisher


def _parse_tags(tags):
    if isinstance(tags, str):
        try:
            return json.loads(tags)
        except Exception:
            return []
    return tags or []


class AITagsView(APIView):
    def get(self, request, person_id):
        person = get_person_with_connections(person_id)
        if not person:
            return Response({"error": "Person not found"}, status=status.HTTP_404_NOT_FOUND)

        current = None
        if person.get("ai_tagged_at"):
            current = {
                "tags": _parse_tags(person.get("ai_tags")),
                "persona": person.get("ai_persona"),
                "product_fit": person.get("ai_product_fit"),
                "urgency": person.get("ai_urgency"),
                "reasoning": person.get("ai_reasoning"),
                "suggested_stage": person.get("ai_suggested_stage"),
                "confidence": person.get("ai_confidence"),
                "ai_tagged_at": person.get("ai_tagged_at"),
                "ai_tag_status": person.get("ai_tag_status"),
                "model_used": person.get("ai_model_used"),
                "tokens_used": person.get("ai_tokens_used"),
            }

        history = get_ai_tag_history(person_id)

        return Response({
            "current": current,
            "history": history,
            "override": None,
        })

    def patch(self, request, person_id):
        data = request.data
        override_note = data.get("override_note", "")
        if not override_note:
            return Response({"error": "override_note is required"}, status=status.HTTP_400_BAD_REQUEST)

        update_ai_tags(person_id, {
            "tags": data.get("tags", []),
            "persona": data.get("persona", ""),
            "product_fit": data.get("product_fit", ""),
            "urgency": data.get("urgency", "medium"),
            "reasoning": override_note,
            "ai_tag_status": "overridden",
            "ai_tagged_at": datetime.now(timezone.utc).isoformat(),
            "suggested_stage": data.get("suggested_stage", ""),
            "confidence": data.get("confidence", 1.0),
            "model_used": "human",
            "tokens_used": 0,
        })

        # Broadcast override via WebSocket
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "crm_live_feed",
                {
                    "type": "ai_tags_overridden",
                    "person_id": person_id,
                    "by": request.user.username if request.user.is_authenticated else "unknown",
                },
            )
        except Exception:
            pass

        return Response({"status": "updated", "ai_tag_status": "overridden"})


class AITagsRetagView(APIView):
    def post(self, request, person_id):
        requested_by = request.user.username if request.user.is_authenticated else "anonymous"

        try:
            event = AITagRequestEvent(person_id=person_id, requested_by=requested_by)
            with CRMPublisher() as pub:
                pub.publish_ai_tag_request(event)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"status": "queued", "message": "Re-analysis in progress..."})
