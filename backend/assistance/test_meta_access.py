"""Who may use Meta endpoints (care.consent.meta_user_allowed / meta_account_denial).

Production default is public access for every active adult account; eligibility is not authorization, each request
still needs the person's own grants. The allow-list is only an explicit operator mode for staged testing.
"""

import os
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from care.consent import meta_access, meta_user_allowed
from care.models import Profile
from care.testing import adult
from config.asgi import application
from assistance.test_captions import FakeMeta


PROD_META = {"AINGEL_ENV": "production", "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}
ALLOWLIST = {**PROD_META, "AINGEL_META_ACCESS": "allowlist"}


class PublicAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = adult(get_user_model().objects.create_user(username="public-adult"))
        self.profile = Profile.objects.create(owner=self.user, display_name="Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_every_active_adult_account_is_eligible_without_any_list(self):
        second = adult(get_user_model().objects.create_user(username="second-public-adult"))
        with patch.dict(os.environ, PROD_META):
            self.assertEqual(meta_access(), "public")
            self.assertTrue(meta_user_allowed(self.user))
            self.assertTrue(meta_user_allowed(second))
            self.assertFalse(meta_user_allowed(AnonymousUser()))
            second.is_active = False
            self.assertFalse(meta_user_allowed(second))

    def test_eligibility_is_not_authorization(self):
        with patch.dict(os.environ, PROD_META), patch("assistance.conversation.call_spark") as spark:
            # Eligible, but the person granted nothing and the server only runs fixtures without real-data mode.
            response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hola"}]}, format="json")
            self.assertEqual(response.data["error"], "privacy_review_required")
            spark.assert_not_called()

    def test_an_account_without_the_adult_declaration_is_refused(self):
        minor = get_user_model().objects.create_user(username="no-declaration")
        profile = Profile.objects.create(owner=minor, display_name="Sin declaración")
        client = APIClient()
        client.force_authenticate(minor)
        with patch.dict(os.environ, PROD_META), patch("assistance.conversation.call_spark") as spark:
            response = client.post(f"/api/v1/profiles/{profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
            self.assertEqual((response.status_code, response.data["error"]), (403, "adult_declaration_required"))
            spark.assert_not_called()


class AllowlistModeTests(TestCase):
    """The explicit staged-testing mode: only listed numeric account IDs."""

    def setUp(self):
        cache.clear()
        self.user = adult(get_user_model().objects.create_user(username="allowed-test"))
        self.profile = Profile.objects.create(owner=self.user, display_name="Test")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_empty_allowlist_denies_all_meta_http_endpoints_before_provider(self):
        base = f"/api/v1/profiles/{self.profile.pk}/"
        urls = ["/api/v1/scene/", "/api/v1/locate/", "/api/v1/vision/", "/api/v1/documents/", base + "companion/chat/",
                base + "conversation/", base + "signs/gloss/"]
        with patch.dict(os.environ, {**ALLOWLIST, "AINGEL_META_ALLOWED_USER_IDS": ""}), patch("assistance.conversation.call_spark") as spark, patch("assistance.scene.httpx.Client") as scene, patch("assistance.locate.httpx.Client") as locate, patch("assistance.vision.httpx.Client") as vision:
            for url in urls:
                response = self.client.post(url, {}, format="json")
                self.assertEqual(response.status_code, 403, url)
                self.assertEqual(response.data["error"], "meta_access_denied")
            for provider in (spark, scene, locate, vision):
                provider.assert_not_called()

    def test_numeric_account_id_required_and_mock_is_unaffected(self):
        with patch.dict(os.environ, {**ALLOWLIST, "AINGEL_META_ALLOWED_USER_IDS": f"bad, {self.user.pk + 1}"}):
            self.assertFalse(meta_user_allowed(self.user))
        with patch.dict(os.environ, {**ALLOWLIST, "AINGEL_META_ALLOWED_USER_IDS": "*"}):
            self.assertFalse(meta_user_allowed(self.user))  # no wildcard: «public» is its own explicit mode
        with patch.dict(os.environ, {**ALLOWLIST, "AINGEL_META_ALLOWED_USER_IDS": f" {self.user.pk}, 9999 "}):
            self.assertTrue(meta_user_allowed(self.user))
            with patch("assistance.conversation.call_spark", return_value={"mode": "meta", "model": "test", "text": "ok"}) as spark:
                response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
                self.assertEqual(response.status_code, 200)
                spark.assert_called_once()
        with patch.dict(os.environ, {**ALLOWLIST, "AINGEL_AI_MODE": "mock", "AINGEL_META_ALLOWED_USER_IDS": ""}):
            response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hello"}]}, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["mode"], "mock")


class MetaWebsocketAccessTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = adult(get_user_model().objects.create_user(username="ws-test"))
        self.client.force_login(self.user)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    def socket(self):
        return WebsocketCommunicator(application, "/ws/captions/", headers=[(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)])

    @patch.dict(os.environ, {**ALLOWLIST, "AINGEL_META_ALLOWED_USER_IDS": ""})
    async def test_websocket_allowlist_fails_before_provider_connection(self):
        with patch("assistance.captions.connect", new=AsyncMock()) as connect:
            ws = self.socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC"})
            self.assertEqual((await ws.receive_json_from())["code"], "meta_access_denied")
            connect.assert_not_called()
            await ws.disconnect()

    @patch.dict(os.environ, PROD_META)
    async def test_websocket_public_needs_grants_and_never_trusts_a_declaration(self):
        with patch("assistance.captions.connect", new=AsyncMock(return_value=FakeMeta())) as connect:
            ws = self.socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC"})
            self.assertEqual((await ws.receive_json_from())["code"], "privacy_review_required")
            await ws.disconnect()
            for extra in ({"synthetic": True}, {"fixture": "greeting"}):
                ws = self.socket()
                self.assertTrue((await ws.connect())[0])
                await ws.send_json_to({"type": "start", "locale": "es-EC", **extra})
                self.assertEqual((await ws.receive_json_from())["code"], "synthetic_captions_unavailable", extra)
                await ws.disconnect()
            ws = self.socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC", "source": "speakers"})
            self.assertEqual((await ws.receive_json_from())["code"], "caption_control_invalid")
            await ws.disconnect()
            connect.assert_not_called()
