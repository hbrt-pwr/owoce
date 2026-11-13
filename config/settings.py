"""Ustawienia projektu Owocownik.

Lokalnie (DEV) wszystko działa bez zmiennych środowiskowych: SQLite, DEBUG, zdjęcia w media/.
W chmurze (L3/L4) konfiguracja przychodzi ze zmiennych środowiskowych – patrz docs/L3-architektura.md:
  DJANGO_DEBUG=0, DJANGO_SECRET_KEY, DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS,
  DATABASE_URL (PostgreSQL), AZURE_ACCOUNT_NAME / AZURE_ACCOUNT_KEY / AZURE_CONTAINER (zdjęcia).
"""
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=""):
    return [x.strip() for x in os.environ.get(name, default).split(",") if x.strip()]


DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Ustaw DJANGO_SECRET_KEY (produkcja nie może używać klucza deweloperskiego).")
    SECRET_KEY = "django-insecure-local-dev-only-change-me-7f3k2l9q"

# Domena publiczna, np. owoce.example.pl (lista po przecinku).
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
# Formularze wysyłane z HTTPS na domenie publicznej, np. https://owoce.example.pl
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "fruits",
]

MIDDLEWARE = [
    # Musi być pierwszy: odpowiada sondzie load balancera przed sprawdzaniem nagłówka Host.
    "fruits.health.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Limit żądań na IP – przed sesją i bazą danych, żeby zalew żądań był odrzucany tanio (fruits/ratelimit.py).
    "fruits.ratelimit.RateLimitMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

if not DEBUG:
    # Pliki statyczne serwuje sama aplikacja (każda instancja ma je w obrazie) – bez współdzielonego dysku.
    # Lokalnie robi to runserver.
    MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "fruits.context_processors.nav",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Baza: bez DATABASE_URL lokalny SQLite, w chmurze współdzielony PostgreSQL
# (np. postgres://user:haslo@host:5432/owoce?sslmode=require). Wszystkie instancje aplikacji
# łączą się z tą samą bazą, więc można je dowolnie dokładać i usuwać.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

# Cache: "default" w pamięci procesu (ogólny limit żądań na IP), "ratelimit" w bazie – wspólny dla wszystkich
# instancji (limity logowania, rejestracji, resetu hasła). Tabelę tworzy `createcachetable` (robi to init_db).
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "ratelimit": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "ratelimit_cache",
        "OPTIONS": {"MAX_ENTRIES": 20000},
    },
}
RATELIMIT_ENABLED = os.environ.get("DJANGO_RATELIMIT", "1") == "1"

# Polityka haseł: min. 10 znaków + wielka litera, mała litera, cyfra i znak specjalny.
# Kolejność = kolejność punktów na liście wymogów przy rejestracji / resecie hasła.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "fruits.validators.CharacterClassValidator", "OPTIONS": {"kind": "upper"}},
    {"NAME": "fruits.validators.CharacterClassValidator", "OPTIONS": {"kind": "lower"}},
    {"NAME": "fruits.validators.CharacterClassValidator", "OPTIONS": {"kind": "digit"}},
    {"NAME": "fruits.validators.CharacterClassValidator", "OPTIONS": {"kind": "symbol"}},
]

# Sesje trzymane w bazie danych, ważne 2 tygodnie. Baza jest wspólna dla wszystkich instancji,
# więc load balancer nie potrzebuje „sticky sessions” – każde zapytanie może trafić gdziekolwiek.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True

# E-maile (link „Nie pamiętasz hasła?”). Serwer SMTP ze zmiennych środowiskowych; hasło SMTP trzymamy
# w sekrecie Container Apps. Bez EMAIL_HOST wiadomości trafiają na standardowe wyjście – lokalnie link
# do resetu widać w terminalu runserver, w Azure w logach aplikacji (nikt go nie dostanie mailem).
if os.environ.get("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_SSL = EMAIL_PORT == 465  # 465 = SSL od początku, 587 = STARTTLS
    EMAIL_USE_TLS = not EMAIL_USE_SSL
    EMAIL_TIMEOUT = 15
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "Owocownik <kontakt@owocownik.pl>")
# Link „Nie pamiętasz hasła?” jest ważny godzinę (domyślnie w Django 3 dni).
PASSWORD_RESET_TIMEOUT = 60 * 60
# Link potwierdzający adres e-mail po rejestracji – ważny dobę, potem niepotwierdzone konto jest usuwane.
ACCOUNT_CONFIRMATION_TIMEOUT = 60 * 60 * 24

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

LANGUAGE_CODE = "pl"
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"  # wynik collectstatic (budowany w obrazie Dockera)

# Zdjęcia owoców wgrywane przez panel admina. Lokalnie folder media/, w chmurze Azure Blob Storage –
# instancje za load balancerem nie mają wspólnego dysku, a zdjęcie wgrane na jednej musi być widoczne na wszystkich.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
if os.environ.get("AZURE_ACCOUNT_NAME"):
    azure_options = {
        "account_name": os.environ["AZURE_ACCOUNT_NAME"],
        "azure_container": os.environ.get("AZURE_CONTAINER", "media"),
        "overwrite_files": False,
    }
    if os.environ.get("AZURE_ACCOUNT_KEY"):
        azure_options["account_key"] = os.environ["AZURE_ACCOUNT_KEY"]
    else:
        # Bez klucza: aplikacja loguje się do Storage swoją tożsamością zarządzaną (Managed Identity)
        # z rolą „Storage Blob Data Contributor” – w Azure nie ma żadnego klucza do przechowywania.
        from azure.identity import DefaultAzureCredential

        azure_options["token_credential"] = DefaultAzureCredential()
    STORAGES["default"] = {"BACKEND": "storages.backends.azure_storage.AzureStorage", "OPTIONS": azure_options}

# --- Aplikacja za load balancerem, który kończy TLS ---
# Certyfikat jest na load balancerze (nie na serwerze aplikacji). Do aplikacji ruch idzie już po HTTP
# w sieci prywatnej, a load balancer dopisuje X-Forwarded-Proto: https i X-Forwarded-Host.
# Ufamy tym nagłówkom tylko dlatego, że aplikacja nie jest wystawiona do internetu bezpośrednio.
if os.environ.get("DJANGO_BEHIND_PROXY", "0" if DEBUG else "1") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    # Adres klienta dla limitu żądań: ostatni wpis X-Forwarded-For (dopisany przez ingress).
    RATELIMIT_USE_X_FORWARDED_FOR = True

if not DEBUG:
    # Przeglądarka zawsze rozmawia z nami po HTTPS (przekierowanie HTTP -> HTTPS robi load balancer).
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS: przeglądarka przez rok sama zamienia http:// na https:// (w Azure też ustawione zmienną środowiskową).
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", str(60 * 60 * 24 * 365)))
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Logi na standardowe wyjście – zbiera je platforma (Azure Monitor / Log Analytics), a nie plik na instancji.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
