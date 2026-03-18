from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.models import ExternalApp


class ExternalAppKeyAuthentication(BaseAuthentication):
    """Authenticate external apps via X-API-Key header."""

    def authenticate(self, request):
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return None
        try:
            app = ExternalApp.objects.get(api_key=api_key, is_active=True)
        except ExternalApp.DoesNotExist:
            raise AuthenticationFailed("Invalid or inactive API key")
        request.external_app = app
        return (None, app)
