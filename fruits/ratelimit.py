"""Ograniczanie liczby żądań (rate limiting) – ochrona przed celowym spamowaniem, nie przed zwykłym ruchem.

Dwa poziomy, liczone w oknach czasowych (np. „najwyżej 600 żądań na minutę”):
- ogólny limit na adres IP dla każdego żądania – w pamięci procesu (cache "default"). Liczy osobno każdy proces
  gunicorna, ale przy zalewie żądań nie dokłada pracy bazie danych;
- limity na wysyłanie wrażliwych formularzy (logowanie, rejestracja, reset hasła…) – we wspólnym cache w bazie
  (cache "ratelimit"), więc obowiązują łącznie na wszystkich instancjach za load balancerem.

Limity są celowo luźne: z jednego IP (np. sieć uczelni za NAT) może korzystać wiele osób naraz.
Gdy cache nie działa (np. brak tabeli), żądanie przechodzi – limit nie może zablokować całej strony.
"""
import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import caches
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string

log = logging.getLogger(__name__)

# (limit, okno w sekundach) dla wszystkich żądań z jednego IP
GLOBAL_LIMIT = (600, 60)

# Wysyłanie formularzy (POST), wg nazwy widoku: lista (limit, okno w s, z czego klucz)
POST_LIMITS = {
    "login": [(50, 300, "ip"), (10, 300, "ip+username")],
    "admin:login": [(50, 300, "ip"), (10, 300, "ip+username")],
    "signup": [(20, 3600, "ip")],
    "password_reset": [(10, 3600, "ip"), (3, 3600, "email")],  # bez zasypywania czyjejś skrzynki mailami
    "password_reset_confirm": [(30, 300, "ip")],
    "password_check": [(300, 60, "ip")],  # lista wymogów hasła sprawdza się w trakcie pisania
}
DEFAULT_POST_LIMIT = [(60, 60, "ip+user")]  # oceny, komentarze, usuwanie itd.


def client_ip(request):
    """Adres klienta. Za ingressem Container Apps prawdziwy adres to OSTATNI wpis X-Forwarded-For
    (dopisuje go ingress) – wcześniejsze wpisy może podać sam klient, więc są ignorowane."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if getattr(settings, "RATELIMIT_USE_X_FORWARDED_FOR", False) and forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _key_value(request, ip, kind):
    if kind == "ip":
        return ip
    if kind == "ip+username":
        return f"{ip}|{request.POST.get('username', '').strip().lower()}"
    if kind == "email":
        email = request.POST.get("email", "").strip().lower()
        return email or None  # pusty formularz liczy się tylko w limicie na IP
    if kind == "ip+user":
        user = getattr(request, "user", None)
        return f"user:{user.pk}" if user is not None and user.is_authenticated else ip
    raise ValueError(kind)


def _hit(cache, name, value, limit, window):
    """Zalicza żądanie; zwraca liczbę sekund do końca okna, jeśli limit przekroczony, inaczej None."""
    now = time.time()
    digest = hashlib.sha256(value.encode()).hexdigest()[:32]  # w cache nie trzymamy adresów IP ani e-maili
    key = f"rl:{name}:{digest}:{int(now // window)}"
    if cache.add(key, 1, window + 5):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:  # wpis właśnie wygasł
            cache.set(key, 1, window + 5)
            count = 1
    if count <= limit:
        return None
    if count == limit + 1:  # logujemy tylko pierwsze przekroczenie w oknie, żeby zalew nie zalał też logów
        log.warning("Rate limit %s przekroczony (%s żądań / %s s)", name, limit, window)
    return max(1, int(window - now % window))


def _too_many(request, retry_after):
    if request.path.startswith("/rejestracja/sprawdz-haslo"):
        response = JsonResponse({"error": "too_many_requests"}, status=429)
    else:
        # bez szablonu bazowego i context processorów – odpowiedź ma być tania także pod obciążeniem
        response = HttpResponse(render_to_string("429.html", {"retry_after": retry_after}), status=429)
    response["Retry-After"] = str(retry_after)
    return response


class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "RATELIMIT_ENABLED", True):
            try:
                retry = _hit(caches["default"], "all", client_ip(request), *GLOBAL_LIMIT)
            except Exception:
                log.exception("Rate limit (ogólny) nie zadziałał – przepuszczam żądanie")
                retry = None
            if retry:
                return _too_many(request, retry)
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.method != "POST" or not getattr(settings, "RATELIMIT_ENABLED", True):
            return None
        view_name = request.resolver_match.view_name if request.resolver_match else ""
        rules = POST_LIMITS.get(view_name, DEFAULT_POST_LIMIT)
        ip = client_ip(request)
        try:
            cache = caches["ratelimit"]
            for limit, window, kind in rules:
                value = _key_value(request, ip, kind)
                if value is None:
                    continue
                retry = _hit(cache, f"{view_name or 'post'}:{kind}", value, limit, window)
                if retry:
                    return _too_many(request, retry)
        except Exception:
            log.exception("Rate limit (formularze) nie zadziałał – przepuszczam żądanie")
        return None
