"""The Meta quota and the per-account limits against real Redis clients (assistance.meta_quota, DRF throttles).

RedisUnavailableTests always run: Django's real Redis backend pointed at a closed port, as when Redis is down. Every
path must fail closed, before any request to Meta is built or sent.

RealRedisTests run only against a throwaway Redis: AINGEL_TEST_REDIS_URL (e.g. redis://127.0.0.1:6390/15) and
AINGEL_TEST_REDIS_ISOLATED=1. They use a random key prefix and delete only their own keys (never FLUSHDB).
Limits are never raised by these tests: they are set low on purpose.
"""

import os
from types import SimpleNamespace
import threading
import time
import uuid
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import caches
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from care.models import Profile
from care.testing import adult

from . import synthetic
from .companion import CompanionUnavailable, call_spark
from .conversation import ConversationRate
from .meta_quota import MetaQuotaError, bind_account, reserve_meta_call
from .scene import SceneUnavailable, describe_scene

DOWN = "redis://127.0.0.1:1/0"
REDIS_URL = os.environ.get("AINGEL_TEST_REDIS_URL", "")
ISOLATED = bool(REDIS_URL) and os.environ.get("AINGEL_TEST_REDIS_ISOLATED") == "1"
META = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_REAL_DATA": "0"}


def assert_per_account_limit(test):
    """The configured per-account rate of the conversation endpoint (DRF scope «conversation», read from settings,
    not changed by the test): one account goes past it and is refused; another account is not affected.

    (The first version patched ConversationRate.rate, which DRF throttles do not define as a class attribute: the test
    raised AttributeError before any request. That was the failure Astra saw on real Redis.)"""
    limit = ConversationRate().num_requests
    users = get_user_model().objects
    first = adult(users.create_user(username="quota-first"))
    second = adult(users.create_user(username="quota-second"))
    profiles = {user: Profile.objects.create(owner=user, display_name="Ficticio") for user in (first, second)}
    statuses = []
    with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}):
        for user in [first] * (limit + 1) + [second]:
            client = APIClient()
            client.force_authenticate(user)
            statuses.append(client.post(f"/api/v1/profiles/{profiles[user].pk}/conversation/", {"fixture": "greeting"},
                                        format="json").status_code)
    test.assertEqual(statuses, [200] * limit + [429, 200])


class PerAccountLimitTests(TestCase):
    """The same per-account check on the default cache (always runs); RealRedisTests repeats it on Redis."""

    def setUp(self):
        caches["default"].clear()

    def test_per_account_limits_are_per_account(self):
        assert_per_account_limit(self)


def redis_caches(location, prefix):
    options = {"socket_connect_timeout": 1, "socket_timeout": 1}
    return {
        "default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": location, "KEY_PREFIX": prefix + "-default", "OPTIONS": options},
        "meta_quota": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": location, "KEY_PREFIX": prefix + "-quota", "OPTIONS": options},
    }


class RedisUnavailableTests(TestCase):
    def setUp(self):
        self.settings_override = override_settings(PRODUCTION=True, CACHES=redis_caches(DOWN, "down"),
                                                   AINGEL_META_LIMIT_PER_MINUTE=10, AINGEL_META_LIMIT_PER_DAY=100)
        self.settings_override.enable()
        self.env = patch.dict(os.environ, META)
        self.env.start()
        bind_account(SimpleNamespace(pk=1))  # as an endpoint's meta_account_denial does

    def tearDown(self):
        bind_account(None)
        self.env.stop()
        self.settings_override.disable()

    def test_reservation_fails_closed(self):
        with self.assertRaises(MetaQuotaError) as raised:
            reserve_meta_call()
        self.assertEqual(str(raised.exception), "meta_quota_unavailable")

    def test_no_provider_call_without_the_mandatory_limit(self):
        with patch("assistance.companion.httpx.Client") as companion, patch("assistance.scene.httpx.Client") as scene:
            with self.assertRaises(CompanionUnavailable) as chat:
                call_spark("rules", "{}", basis=synthetic.FIXTURE)
            with self.assertRaises(SceneUnavailable) as image:
                describe_scene(synthetic.shapes_image(), "es-EC", synthetic.FIXTURE)
        self.assertEqual((str(chat.exception), str(image.exception)), ("meta_quota_unavailable", "meta_quota_unavailable"))
        companion.assert_not_called()
        scene.assert_not_called()

    def test_per_account_limit_store_down_stops_the_request(self):
        owner = adult(get_user_model().objects.create_user(username="quota-down"))
        profile = Profile.objects.create(owner=owner, display_name="Ficticio")
        client = APIClient(raise_request_exception=False)
        client.force_authenticate(owner)
        with patch("assistance.companion.httpx.Client") as provider:
            response = client.post(f"/api/v1/profiles/{profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
        self.assertEqual(response.status_code, 500)  # the throttle cannot count: the view never runs
        provider.assert_not_called()


@skipUnless(ISOLATED, "needs a throwaway Redis: AINGEL_TEST_REDIS_URL and AINGEL_TEST_REDIS_ISOLATED=1")
class RealRedisTests(TestCase):
    def setUp(self):
        self.prefix = "aingel-test-" + uuid.uuid4().hex[:12]
        self.settings_override = override_settings(PRODUCTION=True, CACHES=redis_caches(REDIS_URL, self.prefix),
                                                   AINGEL_META_LIMIT_PER_MINUTE=3, AINGEL_META_LIMIT_PER_DAY=5)
        self.settings_override.enable()

    def tearDown(self):
        client = caches["meta_quota"]._cache.get_client(write=True)
        for key in client.scan_iter(match=f":*:{self.prefix}*"):
            client.delete(key)
        for key in client.scan_iter(match=f"{self.prefix}*"):
            client.delete(key)
        self.settings_override.disable()

    def keys(self):
        cache = caches["meta_quota"]
        return cache.make_key("aingel:meta-quota:minute"), cache.make_key("aingel:meta-quota:day")

    def reserve_all(self, attempts, account=1):
        outcomes = []
        for _ in range(attempts):
            try:
                reserve_meta_call(account=account)
                outcomes.append("ok")
            except MetaQuotaError as error:
                outcomes.append(str(error))
        return outcomes

    def test_global_minute_limit(self):
        self.assertEqual(self.reserve_all(4), ["ok", "ok", "ok", "meta_quota_exceeded"])

    def test_global_day_limit(self):
        with override_settings(AINGEL_META_LIMIT_PER_MINUTE=100):
            self.assertEqual(self.reserve_all(6), ["ok"] * 5 + ["meta_quota_exceeded"])

    def test_concurrent_reservations_never_exceed_the_limit(self):
        with override_settings(AINGEL_META_LIMIT_PER_MINUTE=10, AINGEL_META_LIMIT_PER_DAY=1000):
            results, start = [], threading.Barrier(40)

            def one():
                start.wait()
                try:
                    reserve_meta_call(account=threading.get_ident() % 5)
                    results.append(True)
                except MetaQuotaError:
                    results.append(False)

            threads = [threading.Thread(target=one) for _ in range(40)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            client = caches["meta_quota"]._cache.get_client(write=True)
            minute, _ = self.keys()
            self.assertEqual(results.count(True), 10)
            self.assertEqual(client.zcard(minute), 10)

    def test_counters_expire_and_the_window_slides(self):
        self.reserve_all(1)
        client = caches["meta_quota"]._cache.get_client(write=True)
        minute, day = self.keys()
        self.assertTrue(0 < client.ttl(minute) <= 61)
        self.assertTrue(0 < client.ttl(day) <= 86401)
        # Entries older than a minute no longer count against the minute limit.
        seconds, micros = client.time()
        old = seconds * 1_000_000 + micros - 61_000_000
        client.zadd(minute, {"old-1": old, "old-2": old, "old-3": old})
        self.assertEqual(self.reserve_all(2), ["ok", "ok"])

    def test_per_account_limits_are_per_account(self):
        assert_per_account_limit(self)

    def test_meta_quota_per_account_on_real_redis(self):
        """Several accounts on real Redis: each has its own counters, and the platform's limit is shared."""
        with override_settings(AINGEL_META_LIMIT_PER_MINUTE=100, AINGEL_META_LIMIT_PER_DAY=6,
                               AINGEL_META_USER_LIMIT_PER_MINUTE=2, AINGEL_META_USER_LIMIT_PER_DAY=50):
            self.assertEqual(self.reserve_all(3, account=101), ["ok", "ok", "meta_account_quota_exceeded"])
            self.assertEqual(self.reserve_all(2, account=102), ["ok", "ok"])  # not affected by account 101
            self.assertEqual(self.reserve_all(3, account=103), ["ok", "ok", "meta_quota_exceeded"])  # platform day full

    def test_losing_redis_mid_run_keeps_failing_closed(self):
        self.assertEqual(self.reserve_all(1), ["ok"])
        with override_settings(CACHES=redis_caches(DOWN, self.prefix)):
            with self.assertRaises(MetaQuotaError) as raised:
                reserve_meta_call(account=1)
        self.assertEqual(str(raised.exception), "meta_quota_unavailable")
        time.sleep(0)  # the real server still holds only the first reservation
        client = caches["meta_quota"]._cache.get_client(write=True)
        self.assertEqual(client.zcard(self.keys()[0]), 1)
