import os
from pathlib import Path
import subprocess
import sys
from ipaddress import ip_network

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase

from config.proxy import TrustedProxyASGI


class ProductionSettingsTests(SimpleTestCase):
    def environment(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AINGEL_", "DJANGO_", "MODEL_"))}
        env.update({
            "AINGEL_ENV": "production",
            "DJANGO_SECRET_KEY": "s" * 64,
            "AINGEL_ENCRYPTION_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
            "AINGEL_ALLOWED_HOSTS": "example.test",
            "AINGEL_CSRF_TRUSTED_ORIGINS": "https://example.test",
            "AINGEL_WEBSOCKET_ORIGINS": "https://example.test",
            "AINGEL_TRUSTED_PROXY_NETWORKS": "127.0.0.1/32",
            "AINGEL_DB_NAME": "aingel",
            "AINGEL_DB_USER": "aingel",
            "AINGEL_DB_PASSWORD": "test-password",
            "AINGEL_DB_HOST": "database.example.test",
            "AINGEL_DB_SSLROOTCERT": "/run/secrets/db-ca.pem",
            "AINGEL_REDIS_URL": "rediss://cache.example.test:6379/0",
            "AINGEL_META_REDIS_URL": "rediss://quota.example.test:6379/0",
            "AINGEL_REDIS_CA_CERT": str(Path.cwd().anchor or "/") + "ca.pem",
            "AINGEL_PRIVATE_MEDIA_ROOT": str(Path.cwd().anchor or "/") + "aingel-private",
        })
        return env

    def import_settings(self, env):
        return subprocess.run(
            [sys.executable, "-c", (
                "from config import settings as s; "
                "assert s.PRODUCTION and not s.DEBUG; "
                "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE; "
                "assert s.SECURE_SSL_REDIRECT; "
                "assert s.DATABASES['default']['ENGINE'].endswith('postgresql'); "
                "assert s.DATABASES['default']['OPTIONS']['sslmode'] == 'verify-full'; "
                "assert s.CACHES['default']['BACKEND'].endswith('RedisCache'); "
                "assert s.CACHES['default']['OPTIONS']['ssl_cert_reqs'] == 'required'; "
                "assert s.CACHES['default']['OPTIONS']['ssl_check_hostname'] is True; "
                "assert s.CACHES['default']['OPTIONS']['ssl_ca_certs'] == s.os.environ['AINGEL_REDIS_CA_CERT']; "
                "assert s.CACHES['meta_quota']['OPTIONS']['ssl_check_hostname'] is True; "
                "assert s.CACHES['meta_quota']['LOCATION'] == s.os.environ['AINGEL_META_REDIS_URL']; "
                "assert s.WEBSOCKET_ALLOWED_ORIGINS == ['https://example.test']"
            )], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
        )

    def test_complete_configuration_loads(self):
        result = self.import_settings(self.environment())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_default_ai_mode_is_mock(self):
        result = subprocess.run(
            [sys.executable, "-c", "from config import settings; assert settings.ai_mode == 'mock'"],
            cwd=Path(__file__).resolve().parents[1], env=self.environment(), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_meta_requires_explicit_synthetic_opt_in_and_key(self):
        env = self.environment()
        env.update({"AINGEL_AI_MODE": "meta", "AINGEL_META_SYNTHETIC_TEST_ACK": "1", "MODEL_API_KEY": "test-key"})
        self.assertEqual(self.import_settings(env).returncode, 0)
        for change in ({"AINGEL_META_SYNTHETIC_TEST_ACK": "0"},
                       {"AINGEL_SYNTHETIC_TESTS_ONLY": "0"}, {"MODEL_API_KEY": ""},
                       {"AINGEL_REAL_DATA": "1"}):
            with self.subTest(change=change):
                self.assertNotEqual(self.import_settings({**env, **change}).returncode, 0)

    def test_private_media_mode_requires_exclusive_operator_opt_in(self):
        env = self.environment()
        env.update({"AINGEL_AI_MODE": "meta", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "1", "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "MODEL_API_KEY": "test-key"})
        self.assertEqual(self.import_settings(env).returncode, 0)
        for change in ({"AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}, {"AINGEL_REAL_DATA": "0"},
                       {"AINGEL_SYNTHETIC_TESTS_ONLY": "1"}, {"AINGEL_AI_MODE": "mock"},
                       {"MODEL_API_KEY": ""}):
            with self.subTest(change=change):
                self.assertNotEqual(self.import_settings({**env, **change}).returncode, 0)

    def test_required_values_fail_closed(self):
        for name in ("DJANGO_SECRET_KEY", "AINGEL_ENCRYPTION_KEY", "AINGEL_ALLOWED_HOSTS",
                     "AINGEL_CSRF_TRUSTED_ORIGINS", "AINGEL_WEBSOCKET_ORIGINS",
                     "AINGEL_TRUSTED_PROXY_NETWORKS", "AINGEL_DB_PASSWORD", "AINGEL_DB_SSLROOTCERT",
                     "AINGEL_REDIS_URL", "AINGEL_META_REDIS_URL", "AINGEL_REDIS_CA_CERT", "AINGEL_PRIVATE_MEDIA_ROOT"):
            with self.subTest(name=name):
                env = self.environment()
                env.pop(name)
                self.assertNotEqual(self.import_settings(env).returncode, 0)

    def test_redis_cannot_override_certificate_verification_via_url(self):
        env = self.environment()
        env["AINGEL_REDIS_URL"] = "rediss://cache.example.test:6379/0?ssl_cert_reqs=none"
        self.assertNotEqual(self.import_settings(env).returncode, 0)
        env = self.environment()
        env["AINGEL_META_REDIS_URL"] = "rediss://quota.example.test:6379/0?ssl_cert_reqs=none"
        self.assertNotEqual(self.import_settings(env).returncode, 0)
        env = self.environment()
        env["AINGEL_META_REDIS_URL"] = env["AINGEL_REDIS_URL"]
        self.assertNotEqual(self.import_settings(env).returncode, 0)

    def test_unsafe_settings_rejected(self):
        cases = {
            "DJANGO_DEBUG": "1", "DJANGO_SECRET_KEY": "short", "AINGEL_ENCRYPTION_KEY": "bad",
            "AINGEL_ALLOWED_HOSTS": "*", "AINGEL_CSRF_TRUSTED_ORIGINS": "http://example.test",
            "AINGEL_WEBSOCKET_ORIGINS": "https://elsewhere.test", "AINGEL_TRUSTED_PROXY_NETWORKS": "0.0.0.0/0",
            "AINGEL_REDIS_URL": "redis://cache.example.test:6379/0", "AINGEL_REDIS_CA_CERT": "relative", "AINGEL_AI_MODE": "meta",
            "AINGEL_REAL_DATA": "1", "AINGEL_HSTS_SECONDS": "-1", "AINGEL_PRIVATE_MEDIA_ROOT": "relative",
            "AINGEL_META_LIMIT_PER_DAY": "-1", "AINGEL_META_LIMIT_PER_MINUTE": "not-a-number",
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                env = self.environment()
                env[name] = value
                self.assertNotEqual(self.import_settings(env).returncode, 0)


class TrustedProxyTests(SimpleTestCase):
    def exercise(self, scope):
        received, sent = [], []

        async def inner(inner_scope, receive, send):
            received.append(inner_scope)

        async def receive():
            return {}

        async def send(message):
            sent.append(message)

        proxy = TrustedProxyASGI(inner, [ip_network("127.0.0.1/32")])
        async_to_sync(proxy)(scope, receive, send)
        return received, sent

    def scope(self, kind="http"):
        return {"type": kind, "client": ("127.0.0.1", 123), "headers": [
            (b"x-real-ip", b"203.0.113.9"), (b"x-forwarded-proto", b"https"),
        ]}

    def test_trusted_proxy_passes_real_client_and_scheme_for_http_and_websocket(self):
        for kind, scheme in (("http", "https"), ("websocket", "wss")):
            with self.subTest(kind=kind):
                received, sent = self.exercise(self.scope(kind))
                self.assertEqual(sent, [])
                self.assertEqual(received[0]["client"][0], "203.0.113.9")
                self.assertEqual(received[0]["scheme"], scheme)

    def test_untrusted_or_ambiguous_headers_are_rejected(self):
        cases = []
        scope = self.scope(); scope["client"] = ("198.51.100.7", 123); cases.append(scope)
        scope = self.scope(); scope["headers"] = []; cases.append(scope)
        scope = self.scope(); scope["headers"].append((b"x-real-ip", b"203.0.113.10")); cases.append(scope)
        scope = self.scope(); scope["headers"][1] = (b"x-forwarded-proto", b"http"); cases.append(scope)
        scope = self.scope(); scope["headers"][0] = (b"x-real-ip", b"203.0.113.9, 198.51.100.7"); cases.append(scope)
        for scope in cases:
            with self.subTest(scope=scope):
                received, sent = self.exercise(scope)
                self.assertEqual(received, [])
                self.assertEqual(sent[0]["status"], 403)
        scope = self.scope("websocket"); scope["headers"] = []
        received, sent = self.exercise(scope)
        self.assertEqual(received, [])
        self.assertEqual(sent[0], {"type": "websocket.close", "code": 4403})
