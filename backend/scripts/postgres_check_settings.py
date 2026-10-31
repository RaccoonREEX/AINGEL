"""Settings for scripts/verify_migration_0007_postgres.py: the code's own settings, pointed at an isolated PostgreSQL.

Never used by the application. The database comes from AINGEL_CHECK_DB_* (see the script); production variables are
not read.
"""

import os

from config.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["AINGEL_CHECK_DB"],
        "USER": os.environ.get("AINGEL_CHECK_DB_USER", "aingel_check"),
        "PASSWORD": os.environ.get("AINGEL_CHECK_DB_PASSWORD", ""),
        "HOST": os.environ.get("AINGEL_CHECK_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("AINGEL_CHECK_DB_PORT", "55432"),
    }
}
