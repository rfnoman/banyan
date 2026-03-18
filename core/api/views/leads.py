import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import get_leads, update_lead_stage


def _serialize_lead(p: dict) -> dict:
    tags = p.get("ai_tags")
    if isinstance(tags, str):
        try:
            tags = json.loads(tags)
        except Exception:
            tags = []
    return {**p, "ai_tags": tags or []}


class LeadListView(APIView):
    def get(self, request):
        product = request.query_params.get("product")
        stage = request.query_params.get("stage")
        score_min = request.query_params.get("score_min")
        ai_persona = request.query_params.get("ai_persona")
        limit = int(request.query_params.get("limit", 100))

        leads = get_leads(
            product=product,
            stage=stage,
            score_min=float(score_min) if score_min else None,
            ai_persona=ai_persona,
            limit=limit,
        )
        return Response([_serialize_lead(l) for l in leads])


class LeadStageView(APIView):
    def patch(self, request, person_id):
        new_stage = request.data.get("stage")
        if not new_stage:
            return Response({"error": "stage is required"}, status=status.HTTP_400_BAD_REQUEST)

        updated = update_lead_stage(person_id, new_stage)
        if updated == 0:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"person_id": person_id, "stage": new_stage})
