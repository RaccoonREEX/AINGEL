"""Authorizations given when the account is created (web sign-up), kept on the profile.

camera       AINGEL may use the camera to see for the person.
microphone   AINGEL may listen through the microphone.
meta_data    The person's questions, images, audio and support needs may be sent to Meta to answer.

The apps no longer ask per action: the servers check these flags. Real (non-synthetic) data goes to Meta only
when the operator enables it (AINGEL_REAL_DATA=1) and the profile holds the matching authorizations.
"""

import os

from django.utils import timezone

CONSENT_VERSION = "2026-10-29"
KEYS = ("camera", "microphone", "meta_data")
NEEDS = {
    "conversation": ("meta_data",),
    "image": ("camera", "meta_data"),
    "audio": ("microphone", "meta_data"),
}


def clean_consents(value, user):
    """Validated, stamped consents from a sign-up or settings request; None if the shape is wrong."""
    if not isinstance(value, dict) or set(value) - set(KEYS) or not all(isinstance(value.get(k, False), bool) for k in KEYS):
        return None
    return {
        **{k: value.get(k, False) for k in KEYS},
        "version": CONSENT_VERSION,
        "granted_at": timezone.now().isoformat(),
        "granted_by": user.get_username(),
    }


def real_data_enabled():
    return os.environ.get("AINGEL_REAL_DATA", "0") == "1"


def meta_allowed(profile, kind):
    """True when this profile's real data of [kind] may be sent to Meta."""
    # The private own-media test deliberately does not enable generic personal text,
    # including conversation/gloss, or the broader legacy real-data path.
    if os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0") == "1":
        return False
    consents = (profile.consents or {}) if profile is not None else {}
    return real_data_enabled() and all(consents.get(k) is True for k in NEEDS[kind])


def private_media_allowed(profile, user, kind, declared):
    """Opt-in owner-only test; declaration is not analysis of image or audio content."""
    if kind not in ("image", "audio"):
        return False
    if not (
        os.environ.get("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0") == "1"
        and real_data_enabled()
        and os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") == "0"
        and declared is True
        and profile is not None
        and user.is_authenticated
        and profile.owner_id == user.id
    ):
        return False
    consents = profile.consents or {}
    return all(consents.get(k) is True for k in NEEDS[kind])


def synthetic_allowed(synthetic):
    """The original synthetic-test path: a request declared synthetic on a server limited to tests."""
    return synthetic is True and os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") == "1"
