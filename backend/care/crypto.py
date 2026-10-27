from functools import lru_cache
import os

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@lru_cache(maxsize=1)
def cipher():
    key = os.environ.get("AINGEL_ENCRYPTION_KEY", "").strip()
    if not key:
        if os.environ.get("AINGEL_ENV", "local") != "local":
            raise ImproperlyConfigured(
                "AINGEL_ENCRYPTION_KEY is required outside local mode"
            )
        path = settings.BASE_DIR.parent / ".local" / "encryption.key"
        path.parent.mkdir(exist_ok=True)
        try:
            with path.open("xb") as file:
                file.write(Fernet.generate_key())
        except FileExistsError:
            pass
        key = path.read_bytes()
    return Fernet(key)


def encrypt(value: str):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value: str):
    return cipher().decrypt(value.encode()).decode()
