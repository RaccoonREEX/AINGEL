"""Fail-closed, shared admission for Meta calls; no request content is stored."""

from uuid import uuid4

from django.conf import settings
from django.core.cache import caches


class MetaQuotaError(Exception):
    pass


# Both counters are checked and incremented together on the Redis primary.
# Expiration is set in the same script, so a crash cannot leave immortal keys.
_RESERVE = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) * 1000000 + tonumber(clock[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - 60000000)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now - 86400000000)
local minute = redis.call('ZCARD', KEYS[1])
local day = redis.call('ZCARD', KEYS[2])
local minute_limit = tonumber(ARGV[1])
local day_limit = tonumber(ARGV[2])
if minute >= minute_limit or day >= day_limit then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('EXPIRE', KEYS[1], 61)
redis.call('ZADD', KEYS[2], now, ARGV[3])
redis.call('EXPIRE', KEYS[2], 86401)
return 1
"""


def reserve_meta_call():
    """Reserve before contacting Meta. Limits apply globally, not per process/user.

    Dedicated production Redis uses authenticated TLS and persistent storage.
    Local mode remains usable without Redis and without a hard usage limit.
    """
    if not settings.PRODUCTION:
        return
    try:
        cache = caches["meta_quota"]
        minute_key = cache.make_key("aingel:meta-quota:minute")
        day_key = cache.make_key("aingel:meta-quota:day")
        client = cache._cache.get_client(minute_key, write=True)
        result = client.eval(
            _RESERVE, 2, minute_key, day_key,
            settings.AINGEL_META_LIMIT_PER_MINUTE,
            settings.AINGEL_META_LIMIT_PER_DAY,
            uuid4().hex,
        )
    except Exception:
        # Do not log credentials, request content or provider responses.
        raise MetaQuotaError("meta_quota_unavailable") from None
    if result != 1:
        raise MetaQuotaError("meta_quota_exceeded")
