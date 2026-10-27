import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
# An ephemeral secret permits local scaffold checks. Production requires a stable secret.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or secrets.token_urlsafe(48)
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
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
        "scene": "10/min",
        "face": "6/min",
        "mfa": "6/min",
        "sign": "30/min",
        "chat": "6/min",
    },
}
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
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
