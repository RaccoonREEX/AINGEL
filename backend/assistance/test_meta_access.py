import os
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from care.consent import meta_user_allowed
from care.models import Profile
from config.asgi import application
from assistance.test_captions import FakeMeta


PROD_META = {"AINGEL_ENV": "production", "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}


class MetaAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="allowed-test")
        self.profile = Profile.objects.create(owner=self.user, display_name="Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_empty_allowlist_denies_all_meta_http_endpoints_before_provider(self):
        base = f"/api/v1/profiles/{self.profile.pk}/"
        urls = ["/api/v1/scene/", "/api/v1/locate/", base + "companion/chat/", base + "conversation/", base + "signs/gloss/"]
        with patch.dict(os.environ, {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": ""}), patch("assistance.conversation.call_spark") as spark, patch("assistance.scene.httpx.Client") as scene, patch("assistance.locate.httpx.Client") as locate:
            for url in urls:
                response = self.client.post(url, {}, format="json")
                self.assertEqual(response.status_code, 403, url)
                self.assertEqual(response.data["error"], "meta_access_denied")
            spark.assert_not_called()
            scene.assert_not_called()
            locate.assert_not_called()

    def test_numeric_account_id_required_and_mock_is_unaffected(self):
        with patch.dict(os.environ, {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": f"bad, {self.user.pk + 1}"}):
            self.assertFalse(meta_user_allowed(self.user))
        with patch.dict(os.environ, {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": f" {self.user.pk}, 9999 "}):
            self.assertTrue(meta_user_allowed(self.user))
            with patch("assistance.conversation.call_spark", return_value={"mode": "meta", "model": "test", "text": "ok"}) as spark:
                response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hello"}], "synthetic": True}, format="json")
                self.assertEqual(response.status_code, 200)
                spark.assert_called_once()
        with patch.dict(os.environ, {**PROD_META, "AINGEL_AI_MODE": "mock", "AINGEL_META_ALLOWED_USER_IDS": ""}):
            response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hello"}]}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["mode"], "mock")

    def test_public_wildcard_requires_explicit_synthetic_only_and_active_account(self):
        public = {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": "*", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_REAL_DATA": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
        second = get_user_model().objects.create_user(username="second-demo-user")
        with patch.dict(os.environ, public, clear=True):
            self.assertTrue(meta_user_allowed(self.user))
            self.assertTrue(meta_user_allowed(second))
            self.assertFalse(meta_user_allowed(AnonymousUser()))
            second.is_active = False
            self.assertFalse(meta_user_allowed(second))
            with patch("assistance.conversation.call_spark", return_value={"mode": "meta", "model": "test", "text": "ok"}) as spark:
                response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hello"}], "synthetic": True}, format="json")
                self.assertEqual(response.status_code, 200)
                spark.assert_called_once()
            with patch("assistance.conversation.call_spark") as spark:
                response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hello"}]}, format="json")
                self.assertEqual(response.data["error"], "privacy_review_required")
                spark.assert_not_called()
        for changed in ({"AINGEL_REAL_DATA": "1"}, {"AINGEL_SYNTHETIC_TESTS_ONLY": "0"}, {"AINGEL_PRIVATE_OWN_MEDIA_TEST": "1"}):
            with patch.dict(os.environ, {**public, **changed}, clear=True):
                self.assertFalse(meta_user_allowed(self.user), changed)
        for missing in ("AINGEL_REAL_DATA", "AINGEL_SYNTHETIC_TESTS_ONLY"):
            with patch.dict(os.environ, {k: v for k, v in public.items() if k != missing}, clear=True):
                self.assertFalse(meta_user_allowed(self.user), missing)


class MetaWebsocketAccessTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username="ws-test")
        self.client.force_login(self.user)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    @patch.dict(os.environ, {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": ""})
    async def test_websocket_fails_before_provider_connection(self):
        with patch("assistance.captions.connect", new=AsyncMock()) as connect:
            ws = WebsocketCommunicator(application, "/ws/captions/", headers=[(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)])
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC", "synthetic": True})
            self.assertEqual((await ws.receive_json_from())["code"], "meta_access_denied")
            connect.assert_not_called()
            await ws.disconnect()

    @patch.dict(os.environ, {**PROD_META, "AINGEL_META_ALLOWED_USER_IDS": "*", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_REAL_DATA": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"})
    async def test_websocket_public_demo_still_requires_synthetic_declaration(self):
        with patch("assistance.captions.connect", new=AsyncMock(return_value=FakeMeta())) as connect:
            def socket():
                return WebsocketCommunicator(application, "/ws/captions/", headers=[(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)])
            ws = socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC", "synthetic": False})
            self.assertEqual((await ws.receive_json_from())["code"], "privacy_review_required")
            connect.assert_not_called()
            await ws.disconnect()
            ws = socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC", "synthetic": True})
            self.assertEqual((await ws.receive_json_from())["type"], "ready")
            connect.assert_awaited_once()
            await ws.disconnect()
