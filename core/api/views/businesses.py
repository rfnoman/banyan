from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from core.db.queries import get_all_businesses, create_or_merge_business, get_business_by_id


class BusinessListView(APIView):
    def get(self, request):
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))
        businesses = get_all_businesses(limit=limit, offset=offset)
        return Response(businesses)

    def post(self, request):
        data = request.data
        if not data.get("name"):
            return Response({"error": "name is required"}, status=status.HTTP_400_BAD_REQUEST)
        business_id = create_or_merge_business(data)
        return Response({"id": business_id, **data}, status=status.HTTP_201_CREATED)


class BusinessDetailView(APIView):
    def get(self, request, business_id):
        business = get_business_by_id(business_id)
        if not business:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(business)
