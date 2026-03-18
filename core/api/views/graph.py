from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.graph.queries import get_graph_snapshot
from core.db.queries import link_person_to_business


class GraphSnapshotView(APIView):
    def get(self, request):
        snapshot = get_graph_snapshot()
        return Response(snapshot)


class GraphEdgeView(APIView):
    def post(self, request):
        source_id = request.data.get("source_id")
        target_id = request.data.get("target_id")
        rel_type = request.data.get("type", "KNOWS")

        if not source_id or not target_id:
            return Response({"error": "source_id and target_id are required"}, status=status.HTTP_400_BAD_REQUEST)

        from core.graph.driver import get_driver
        driver = get_driver()
        with driver.session() as session:
            session.run(
                f"MATCH (a {{id: $src}}) MATCH (b {{id: $tgt}}) MERGE (a)-[:{rel_type}]->(b)",
                src=source_id,
                tgt=target_id,
            )
        return Response({"source_id": source_id, "target_id": target_id, "type": rel_type}, status=status.HTTP_201_CREATED)
