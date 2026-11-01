"""Fail-closed, shared admission for Meta calls; no request content is stored.

Two sets of limits are checked and counted together, atomically, on the Redis primary: the platform's (a safety
net for the shared credits and the VPS) and each account's (so one account, a bot or a loop cannot use up what
everyone shares). Every Meta call counts: a deep description is three calls. Heavy requests (deep vision,
documents) also take one in-flight slot per account. None of this shortens answers: it only refuses or delays
requests beyond the limits.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache as default_cache
from django.core.cache import caches


class MetaQuotaError(Exception):
    pass


# The account responsible for the Meta calls of the current request, set by care.consent.meta_account_denial
# (every Meta endpoint calls it first) and cleared around each request by AccountScope.
_account = ContextVar("aingel_meta_account", default=None)


def bind_account(user):
    _account.set(user.pk if user is not None else None)


def bound_account():
    return _account.get()


class AccountScope:
    """Middleware: no request inherits the account of an earlier one handled by the same worker."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _account.set(None)
        try:
            return self.get_response(request)
        finally:
            _account.reset(token)


# Platform keys 1-2 and account keys 3-4 are checked first and incremented only if all have room. Expiration is set
# in the same script, so a crash cannot leave immortal keys. Returns 1, or -1 (platform) / -2 (account) when full.
_RESERVE = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
local windows = {60000000, 86400000000, 60000000, 86400000000}
local ttl = {61, 86401, 61, 86401}
for i = 1, #KEYS do redis.call('ZREMRANGEBYSCORE', KEYS[i], '-inf', now - windows[i]) end
for i = 1, #KEYS do
  if redis.call('ZCARD', KEYS[i]) >= tonumber(ARGV[i]) then
    if i <= 2 then return -1 else return -2 end
  end
end
for i = 1, #KEYS do
  redis.call('ZADD', KEYS[i], now, ARGV[5])
  redis.call('EXPIRE', KEYS[i], ttl[i])
end
return 1
"""


def reserve_meta_call(account=None):
    """Reserve one Meta call before contacting Meta, for [account] (or the request's bound account).

    Dedicated production Redis uses authenticated TLS and persistent storage. In production a call without an
    account is refused (fail closed). Local mode remains usable without Redis and without a hard usage limit.
    """
    if not settings.PRODUCTION:
        return
    account = account if account is not None else bound_account()
    if account is None:
        raise MetaQuotaError("meta_account_required")
    try:
        cache = caches["meta_quota"]
        keys = [cache.make_key(name) for name in (
            "aingel:meta-quota:minute", "aingel:meta-quota:day",
            f"aingel:meta-quota:account:{account}:minute", f"aingel:meta-quota:account:{account}:day",
        )]
        client = cache._cache.get_client(keys[0], write=True)
        result = client.eval(
            _RESERVE, 4, *keys,
            settings.AINGEL_META_LIMIT_PER_MINUTE, settings.AINGEL_META_LIMIT_PER_DAY,
            settings.AINGEL_META_USER_LIMIT_PER_MINUTE, settings.AINGEL_META_USER_LIMIT_PER_DAY,
            uuid4().hex,
        )
    except Exception:
        # Do not log credentials, request content or provider responses.
        raise MetaQuotaError("meta_quota_unavailable") from None
    if result == -2:
        raise MetaQuotaError("meta_account_quota_exceeded")
    if result != 1:
        raise MetaQuotaError("meta_quota_exceeded")


@contextmanager
def meta_slot(account=None, seconds=240):
    """One heavy Meta request in flight per account (deep vision, documents): a second one waits for the first
    instead of piling up. The slot expires on its own if a worker dies."""
    account = account if account is not None else bound_account()
    if account is None:
        yield
        return
    key = f"aingel:meta-slot:{account}"
    if not default_cache.add(key, 1, seconds):
        raise MetaQuotaError("meta_busy")
    try:
        yield
    finally:
        default_cache.delete(key)
