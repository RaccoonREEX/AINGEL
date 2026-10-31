"""Settings for scripts/serve_https_check.py: this code over real HTTPS on loopback, with production's cookie and CSRF
rules, a throwaway database and no Meta. Never used by the application or in production."""

import os

from config.settings import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
# Same-origin HTTPS writes only: no extra trusted origins, so Django checks Origin against https://<host> itself.
CSRF_TRUSTED_ORIGINS = []
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ["AINGEL_HTTPS_CHECK_DB"]}}
