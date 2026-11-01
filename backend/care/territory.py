"""Meta's Restricted Territories (Meta Model API Model Designation and Geographic Use Policy, 12 Oct 2026, section 3):
AINGEL may not make its Meta-powered features available to, or knowingly permit access by, people located there.

Proportionate and minimal, like the 18+ declaration (care.consent):
- every account declares, for the current policy version, whether it is located in one of those territories; only
  that answer is kept, never the country or a location. Declaring «inside» refuses sign-up and, for an existing
  account, closes every Meta endpoint (care.consent.meta_account_denial) until the person declares otherwise;
- optionally, when the reverse proxy sets a country code from the connection (AINGEL_GEO_COUNTRY_HEADER, e.g. from a
  GeoIP module), a request from a restricted country is refused as well. Crimea, Donetsk and Luhansk cannot be told
  apart from the rest of Ukraine by country code, so for them only the declaration applies.
No account is approved by hand and no list of accounts exists: eligible accounts keep general access.
"""

import os
import re
from contextvars import ContextVar

POLICY_VERSION = "2026-10-12"
OUTSIDE, INSIDE = "outside_restricted", "inside_restricted"

RESTRICTED = {
    "es-EC": "Afganistán, Bielorrusia, Camboya, China (incluidos Hong Kong y Macao), Cuba, Eritrea, Etiopía, Haití, Irán, "
             "Irak, Libia, Myanmar, Nicaragua, Corea del Norte, Pakistán, Rusia, Somalia, Siria, las regiones de Crimea, "
             "Donetsk y Luhansk de Ucrania, Venezuela y Sáhara Occidental",
    "en-US": "Afghanistan, Belarus, Cambodia, China (including Hong Kong and Macau), Cuba, Eritrea, Ethiopia, Haiti, Iran, "
             "Iraq, Libya, Myanmar, Nicaragua, North Korea, Pakistan, Russia, Somalia, Syria, the Crimea, Donetsk and "
             "Luhansk regions of Ukraine, Venezuela and Western Sahara",
}
# ISO 3166-1 alpha-2 codes of the whole-country Restricted Territories (for a proxy-provided country code).
RESTRICTED_COUNTRIES = frozenset({
    "AF", "BY", "KH", "CN", "HK", "MO", "CU", "ER", "ET", "HT", "IR", "IQ", "LY", "MM", "NI", "KP", "PK", "RU", "SO",
    "SY", "VE", "EH",
})

_country = ContextVar("aingel_request_country", default=None)


def statement(data):
    """The account's answer for the current policy version: OUTSIDE, INSIDE, or None when missing or outdated."""
    if not isinstance(data, dict) or data.get("territory_version") != POLICY_VERSION:
        return None
    return data.get("territory") if data.get("territory") in (OUTSIDE, INSIDE) else None


def declared(user):
    """OUTSIDE or INSIDE as the account declared it for the current policy version; None otherwise."""
    if user is None or not getattr(user, "is_authenticated", False) or user.pk is None:
        return None
    from .models import AccountPolicy

    policy = AccountPolicy.objects.filter(user=user, territory_version=POLICY_VERSION).values_list("territory", flat=True).first()
    return policy if policy in (OUTSIDE, INSIDE) else None


def declare(user, answer):
    from django.utils import timezone

    from .models import AccountPolicy

    AccountPolicy.objects.update_or_create(user=user, defaults={
        "territory": answer, "territory_version": POLICY_VERSION, "territory_declared_at": timezone.now(),
    })


def header_name():
    """The request header the reverse proxy fills with the connection's country code, or None (not configured)."""
    value = os.environ.get("AINGEL_GEO_COUNTRY_HEADER", "").strip()
    return value if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,63}", value) else None


def restricted_country(code):
    return isinstance(code, str) and code.strip().upper() in RESTRICTED_COUNTRIES


def country_from_meta(meta):
    """The proxy's country code from a Django request.META, when the header is configured."""
    name = header_name()
    return meta.get("HTTP_" + name.upper().replace("-", "_")) if name else None


def country_from_scope(headers):
    """The same from an ASGI scope's headers (websockets)."""
    name = header_name()
    if not name:
        return None
    wanted = name.lower().encode("latin-1")
    return next((value.decode("latin-1") for key, value in headers or () if key.lower() == wanted), None)


def bound_country():
    return _country.get()


class RequestCountry:
    """Middleware: binds the proxy's country code for this request only (care.consent.meta_account_denial)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _country.set(country_from_meta(request.META))
        try:
            return self.get_response(request)
        finally:
            _country.reset(token)
