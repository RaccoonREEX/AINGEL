"""Short-lived server state that holds a person's material (a picture, a document), encrypted in the cache.

The cache key is a hash of the token, so the cache never holds the token itself; the value is encrypted with a key
derived from SECRET_KEY, and it expires on its own. Used by follow-up sessions (assistance.vision) and documents
(assistance.documents).
"""

import base64
import hashlib
import json
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.cache import cache


def _cipher(purpose):
    secret = hashlib.sha256(f"aingel.{purpose}|".encode() + settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(secret))


def key(purpose, token):
    return f"aingel:{purpose}:" + hashlib.sha256(token.encode()).hexdigest()


def new_token():
    return secrets.token_urlsafe(24)


def save(purpose, token, state):
    """Stores [state] (JSON) until state["expires"] (epoch seconds)."""
    remaining = state["expires"] - time.time()
    if remaining > 1:
        cache.set(key(purpose, token), _cipher(purpose).encrypt(json.dumps(state).encode()), timeout=round(remaining))


def load(purpose, token, user):
    """The state, or None when it expired, never existed or belongs to another account."""
    if not isinstance(token, str) or not 16 <= len(token) <= 64:
        return None
    stored = cache.get(key(purpose, token))
    if stored is None:
        return None
    try:
        state = json.loads(_cipher(purpose).decrypt(stored))
    except (InvalidToken, ValueError, TypeError):
        return None
    if state.get("user") != user.pk or state.get("expires", 0) <= time.time():
        return None
    return state


def delete(purpose, token):
    cache.delete(key(purpose, token))
