import asyncio
import json
import os
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase

from config.asgi import application
from care.models import Profile


class FakeMeta:
    def __init__(self):
        self.sent = []
        self.queue = asyncio.Queue()
        self.closed = False

    async def send(self, value):
        self.sent.append(value)

    async def recv(self):
        return json.dumps({"sessionId": "synthetic-session"})

    def __aiter__(self):
        return self

    async def __anext__(self):
        value = await self.queue.get()
        if value is None:
            raise StopAsyncIteration
        return value

    async def close(self):
        self.closed = True


class CaptionTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        user = get_user_model().objects.create_user(username="caption-test")
        self.profile = Profile.objects.create(owner=user, display_name="Owner", consents={"microphone": True, "meta_data": True})
        self.client.force_login(user)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    def socket(self, origin=b"http://127.0.0.1:5173", auth=True):
        return WebsocketCommunicator(
            application,
            "/ws/captions/",
            headers=[(b"origin", origin)]
            + ([(b"cookie", self.cookie)] if auth else []),
        )

    async def test_unauthenticated_and_untrusted_origins_denied(self):
        ws = self.socket(auth=False)
        ok, code = await ws.connect()
        self.assertFalse(ok)
        await ws.disconnect()
        ws = self.socket(origin=b"https://untrusted.invalid")
        ok, code = await ws.connect()
        self.assertFalse(ok)
        await ws.disconnect()

    async def test_synthetic_consent_required_before_meta_connection(self):
        ws = self.socket()
        self.assertTrue((await ws.connect())[0])
        await ws.send_json_to({"type": "start", "locale": "es-EC", "synthetic": False})
        self.assertEqual(
            (await ws.receive_json_from())["code"], "privacy_review_required"
        )
        await ws.disconnect()

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0"})
    async def test_private_audio_requires_explicit_declaration_before_upstream(self):
        meta = FakeMeta()
        with patch("assistance.captions.connect", new=AsyncMock(return_value=meta)) as connect:
            ws = self.socket()
            await ws.connect()
            await ws.send_json_to({"type": "start", "locale": "es-EC", "profile": str(self.profile.pk)})
            self.assertEqual((await ws.receive_json_from())["code"], "privacy_review_required")
            connect.assert_not_called()
            await ws.disconnect()
            ws = self.socket()
            await ws.connect()
            await ws.send_json_to({"type": "start", "locale": "es-EC", "profile": str(self.profile.pk), "private_test": True})
            self.assertEqual((await ws.receive_json_from())["type"], "ready")
            connect.assert_awaited_once()
            await ws.disconnect()

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    async def test_meta_handshake_pcm_forwarding_and_partial_events(self):
        meta = FakeMeta()
        with patch("assistance.captions.connect", new=AsyncMock(return_value=meta)):
            ws = self.socket()
            self.assertTrue((await ws.connect())[0])
            await ws.send_json_to(
                {"type": "start", "locale": "es-EC", "synthetic": True}
            )
            self.assertEqual((await ws.receive_json_from())["type"], "ready")
            handshake = json.loads(meta.sent[0])
            self.assertEqual(
                handshake["authorization"]["accessToken"], "Bearer synthetic-key"
            )
            self.assertEqual(handshake["audioEncoding"], "PCM_24KHZ")
            await ws.send_to(bytes_data=b"\x00\x00" * 1920)
            await meta.queue.put(json.dumps({"type": "speechStart", "turnId": 1}))
            self.assertEqual((await ws.receive_json_from())["turnId"], 1)
            await meta.queue.put(
                json.dumps(
                    {
                        "type": "transcript",
                        "transcript": "Synthetic sentence",
                        "final": False,
                    }
                )
            )
            self.assertEqual(
                (await ws.receive_json_from())["transcript"], "Synthetic sentence"
            )
            await ws.send_json_to({"type": "stop"})
            await meta.queue.put(
                json.dumps(
                    {
                        "type": "speechComplete",
                        "turnId": 1,
                        "transcript": "Synthetic sentence.",
                    }
                )
            )
            self.assertEqual((await ws.receive_json_from())["type"], "speechComplete")
            await meta.queue.put(None)
            self.assertEqual((await ws.receive_json_from())["type"], "closed")
            await ws.disconnect()
            self.assertTrue(meta.closed)
            self.assertIn(b"\x00\x00" * 1920, meta.sent)
            self.assertEqual(json.loads(meta.sent[-1]), {"type": "endStream"})

    async def test_unsupported_language_rejected(self):
        ws = self.socket()
        await ws.connect()
        await ws.send_json_to({"type": "start", "locale": "ru-RU", "synthetic": True})
        self.assertEqual(
            (await ws.receive_json_from())["code"], "caption_language_unsupported"
        )
        await ws.disconnect()
