from django.urls import re_path
from core.websocket.consumers import CRMConsumer

websocket_urlpatterns = [
    re_path(r"^ws/crm/$", CRMConsumer.as_asgi()),
]
