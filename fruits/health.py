"""Sonda zdrowia dla load balancera: GET /healthz/.

Load balancer co kilka sekund pyta każdą instancję; instancja, która nie odpowiada 200,
przestaje dostawać ruch, a autoskalowanie może ją wymienić. Sprawdzamy też połączenie z bazą –
instancja bez bazy i tak nie obsłuży użytkownika.

Middleware stoi na początku listy, bo sonda trafia na prywatny adres IP instancji, którego nie ma
w ALLOWED_HOSTS (tam jest tylko domena publiczna) – zwykły widok odrzuciłby ją z błędem 400.
"""
import logging

from django.db import connection
from django.http import JsonResponse

log = logging.getLogger(__name__)

PATH = "/healthz/"


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path != PATH:
            return self.get_response(request)
        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception:
            log.exception("Health check: brak połączenia z bazą")
            return JsonResponse({"status": "error", "db": False}, status=503)
        return JsonResponse({"status": "ok", "db": True})
