import io
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from PIL import Image

from care.models import Profile
from care.testing import adult, authorize
from config.asgi import application
from . import synthetic
from .companion import CompanionUnavailable, call_spark
from .locate import locate_object
from .meta_quota import MetaQuotaError, reserve_meta_call
from .scene import SceneUnavailable, describe_scene


class QuotaAdmissionTests(SimpleTestCase):
    @override_settings(PRODUCTION=True, AINGEL_META_LIMIT_PER_MINUTE=3, AINGEL_META_LIMIT_PER_DAY=8)
    def test_shared_redis_admission_and_fail_closed(self):
        client = Mock()
        fake_cache = SimpleNamespace(
            make_key=lambda key: f"prefix:{key}",
            _cache=SimpleNamespace(get_client=lambda key, write: client),
        )
        with patch("assistance.meta_quota.caches", {"meta_quota": fake_cache}):
            client.eval.return_value = 1
            reserve_meta_call()
            args = client.eval.call_args.args
            self.assertEqual(args[1:6], (2, "prefix:aingel:meta-quota:minute", "prefix:aingel:meta-quota:day", 3, 8))
            self.assertEqual(len(args[6]), 32)
            client.eval.return_value = 0
            with self.assertRaisesMessage(MetaQuotaError, "meta_quota_exceeded"):
                reserve_meta_call()
            client.eval.side_effect = OSError("connection details must not be exposed")
            with self.assertRaisesMessage(MetaQuotaError, "meta_quota_unavailable"):
                reserve_meta_call()

    def test_all_http_provider_calls_fail_before_contact(self):
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), "white").save(buf, "PNG")
        data = buf.getvalue()
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test"}):
            for module, invoke, exception in (
                ("scene", lambda basis: describe_scene(data, "es-EC", basis), SceneUnavailable),
                ("locate", lambda basis: locate_object(data, "cup", basis), SceneUnavailable),
                ("companion", lambda basis: call_spark("instructions", "test", basis=basis), CompanionUnavailable),
            ):
                for basis in (synthetic.FIXTURE, synthetic.REAL):
                    with self.subTest(module=module, basis=basis), patch(f"assistance.{module}.reserve_meta_call", side_effect=MetaQuotaError("meta_quota_exceeded")), patch(f"assistance.{module}.httpx.Client") as provider:
                        with self.assertRaisesMessage(exception, "meta_quota_exceeded"):
                            invoke(basis)
                        provider.assert_not_called()
                # Without a basis decided by a view nothing is reserved nor sent.
                for basis in (True, None, "synthetic"):
                    with self.subTest(module=module, basis=basis), patch(f"assistance.{module}.reserve_meta_call") as reserve, patch(f"assistance.{module}.httpx.Client") as provider:
                        with self.assertRaisesMessage(exception, "privacy_review_required"):
                            invoke(basis)
                        reserve.assert_not_called()
                        provider.assert_not_called()

    @override_settings(PRODUCTION=False)
    def test_local_mode_needs_no_redis(self):
        with patch("assistance.meta_quota.caches") as cache_mock:
            reserve_meta_call()
            cache_mock.__getitem__.assert_not_called()


class QuotaWebSocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        # Declared 18+, as every account must be to reach Meta (care.consent): the quota is what this test checks.
        self.user = adult(get_user_model().objects.create_user(username="quota-ws"))
        # The person's own microphone + voice grants: live captions have no synthetic path.
        self.profile = authorize(Profile.objects.create(owner=self.user, display_name="Quota"), microphone_local=True, meta_voice=True)
        self.client.force_login(self.user)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_REAL_DATA": "1", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"})
    async def test_audio_is_denied_before_opening_provider(self):
        with patch("assistance.captions.reserve_meta_call", side_effect=MetaQuotaError("meta_quota_exceeded")), patch("assistance.captions.connect", new=AsyncMock()) as provider:
            ws = WebsocketCommunicator(application, "/ws/captions/", headers=[(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)])
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to({"type": "start", "locale": "es-EC", "profile": str(self.profile.pk)})
            self.assertEqual((await ws.receive_json_from())["code"], "meta_quota_exceeded")
            provider.assert_not_awaited()
            await ws.disconnect()
