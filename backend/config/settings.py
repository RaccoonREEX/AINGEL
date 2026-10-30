import os
import re
import secrets
from ipaddress import ip_network
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# Local scaffolding has deliberately local-only defaults. Public deployments fail closed.
AINGEL_ENV = os.environ.get("AINGEL_ENV", "local")
if AINGEL_ENV not in {"local", "production"}:
    raise ImproperlyConfigured("AINGEL_ENV must be local or production")
PRODUCTION = AINGEL_ENV == "production"


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"{name} is required in production")
    return value


def required_list(name):
    values = [value.strip() for value in required(name).split(",")]
    if not all(values):
        raise ImproperlyConfigured(f"{name} must be a comma-separated list")
    return values


def https_origins(name):
    origins = required_list(name)
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment or parsed.port == 0
                    or parsed.hostname not in ALLOWED_HOSTS):
                raise ValueError
        except ValueError:
            raise ImproperlyConfigured(f"{name} must contain HTTPS origins on allowed hosts") from None
    return origins


SECRET_KEY = required("DJANGO_SECRET_KEY") if PRODUCTION else (os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48))
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
if PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG must be disabled in production")
    if len(SECRET_KEY) < 50:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must contain at least 50 characters")
    try:
        Fernet(required("AINGEL_ENCRYPTION_KEY").encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ImproperlyConfigured("AINGEL_ENCRYPTION_KEY must be a valid Fernet key") from None
    # Explicit, mutually exclusive opt-ins; neither can classify the content supplied by a client.
    ai_mode = os.environ.get("AINGEL_AI_MODE", "mock")
    real_data = os.environ.get("AINGEL_REAL_DATA", "0")
    synthetic_only = os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1")
    private_media = os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0")
    if ai_mode not in {"mock", "meta"} or real_data not in {"0", "1"} or synthetic_only not in {"0", "1"} or private_media not in {"0", "1"}:
        raise ImproperlyConfigured("Invalid production AI mode configuration")
    if real_data == "1":
        if ai_mode != "meta" or private_media != "1" or synthetic_only != "0":
            raise ImproperlyConfigured("Real-data mode requires the private own-media test configuration")
    elif private_media == "1":
        raise ImproperlyConfigured("Private own-media test requires real-data mode")
    if ai_mode == "meta":
        if real_data == "0" and (os.environ.get("AINGEL_META_SYNTHETIC_TEST_ACK") != "1" or synthetic_only != "1"):
            raise ImproperlyConfigured("Meta synthetic tests require explicit opt-in")
        required("MODEL_API_KEY")
    ALLOWED_HOSTS = required_list("AINGEL_ALLOWED_HOSTS")
    hostname = re.compile(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*")
    if any(not hostname.fullmatch(host) for host in ALLOWED_HOSTS):
        raise ImproperlyConfigured("AINGEL_ALLOWED_HOSTS must contain explicit lowercase hostnames")
    try:
        TRUSTED_PROXY_NETWORKS = tuple(ip_network(value, strict=False) for value in required_list("AINGEL_TRUSTED_PROXY_NETWORKS"))
        if any(network.prefixlen == 0 for network in TRUSTED_PROXY_NETWORKS):
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured("AINGEL_TRUSTED_PROXY_NETWORKS must contain restricted IP networks") from None

ROOT_URLCONF = "config.urls"
INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "assistance",
    "care",
]
MIDDLEWARE = [
    "care.auth.PrivateAPIResponses",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "care.mfa.MFAEpochMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "local.sqlite3",
    }
}
if PRODUCTION:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": required("AINGEL_DB_NAME"),
            "USER": required("AINGEL_DB_USER"),
            "PASSWORD": required("AINGEL_DB_PASSWORD"),
            "HOST": required("AINGEL_DB_HOST"),
            "PORT": os.environ.get("AINGEL_DB_PORT", "5432"),
            "OPTIONS": {"sslmode": "verify-full", "sslrootcert": required("AINGEL_DB_SSLROOTCERT")},
        }
    }
    redis_url = required("AINGEL_REDIS_URL")
    try:
        redis_parts = urlsplit(redis_url)
        if redis_parts.scheme != "rediss" or not redis_parts.hostname or redis_parts.query or redis_parts.fragment:
            raise ValueError
        redis_parts.port  # Validate the optional port without leaking the URL.
    except ValueError:
        raise ImproperlyConfigured("AINGEL_REDIS_URL must be a TLS Redis URL without query options") from None
    # Use a Redis-specific CA rather than replacing the public trust store used for Meta.
    redis_ca = Path(required("AINGEL_REDIS_CA_CERT"))
    if not redis_ca.is_absolute():
        raise ImproperlyConfigured("AINGEL_REDIS_CA_CERT must be an absolute path")
    # URL query options override pool settings in redis-py, so queries are disallowed above.
    CACHES = {"default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": redis_url,
        "OPTIONS": {"ssl_cert_reqs": "required", "ssl_check_hostname": True, "ssl_ca_certs": str(redis_ca)},
    }}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.UserRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {
        "user": "120/min",
        "scene": "20/min",  # continuous watching sends up to 15 a minute, plus «qué ves»
        "face": "6/min",
        "mfa": "6/min",
        "sign": "30/min",
        "chat": "6/min",
        "conversation": "12/min",
        "gloss": "30/min",
    },
}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
WEBSOCKET_ALLOWED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8010"]
if PRODUCTION:
    CSRF_TRUSTED_ORIGINS = https_origins("AINGEL_CSRF_TRUSTED_ORIGINS")
    WEBSOCKET_ALLOWED_ORIGINS = https_origins("AINGEL_WEBSOCKET_ORIGINS")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    try:
        SECURE_HSTS_SECONDS = int(os.environ.get("AINGEL_HSTS_SECONDS", "0"))
        if SECURE_HSTS_SECONDS < 0:
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured("AINGEL_HSTS_SECONDS must be a non-negative integer") from None
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("AINGEL_HSTS_INCLUDE_SUBDOMAINS", "0") == "1"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PRIVATE_MEDIA_ROOT = BASE_DIR / "private-media"
if PRODUCTION:
    PRIVATE_MEDIA_ROOT = Path(required("AINGEL_PRIVATE_MEDIA_ROOT"))
    if not PRIVATE_MEDIA_ROOT.is_absolute():
        raise ImproperlyConfigured("AINGEL_PRIVATE_MEDIA_ROOT must be absolute")
ASGI_APPLICATION = "config.asgi.application"

# The development access logger otherwise records search terms in URLs.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact_api_query": {"()": "care.log_filters.RedactAPIQuery"}},
    "handlers": {
        "redacted_console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_api_query"],
        }
    },
    "loggers": {
        "django.channels.server": {
            "handlers": ["redacted_console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["redacted_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
