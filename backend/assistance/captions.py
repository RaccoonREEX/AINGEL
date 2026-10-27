import asyncio
import contextlib
import json
import os
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.cache import cache
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException


class CaptionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.upstream = None
        self.receiver = None
        self.timer = None
        self.lease = False
        self.ended = False
        self.bytes_sent = 0
        user = self.scope.get("user")
        if not user or not user.is_authenticated or not user.is_active:
            await self.close(code=4401)
            return
        if not await self.valid_epoch():
            await self.close(code=4401)
            return
        self.lease_key = f"captions:{user.pk}"
        if not await cache.aadd(self.lease_key, True, 660):
            await self.close(code=4429)
            return
        self.lease = True
        await self.accept()
        self.timer = asyncio.create_task(self.expire(10))

    @database_sync_to_async
    def valid_epoch(self):
        from care.models import MFADevice

        device = MFADevice.objects.filter(user=self.scope["user"]).first()
        return (
            not device
            or not device.epoch
            or self.scope["session"].get("mfa_epoch") == device.epoch
        )

    async def expire(self, seconds):
        await asyncio.sleep(seconds)
        await self.fail("caption_session_expired")

    async def fail(self, code):
        await self.send(text_data=json.dumps({"type": "error", "code": code}))
        await self.close(code=4400)

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is not None:
            if (
                not self.upstream
                or self.ended
                or not 0 < len(bytes_data) <= 9600
                or len(bytes_data) % 2
            ):
                await self.fail("audio_frame_invalid")
                return
            self.bytes_sent += len(bytes_data)
            if self.bytes_sent > 48000 * 600 or self.bytes_sent > 48000 * (
                time.monotonic() - self.started + 5
            ):
                await self.fail("audio_rate_exceeded")
                return
            try:
                await self.upstream.send(bytes_data)
            except ConnectionClosed:
                await self.fail("transcription_unavailable")
            return
        if not text_data or len(text_data) > 1000:
            await self.fail("caption_control_invalid")
            return
        try:
            value = json.loads(text_data)
        except ValueError:
            await self.fail("caption_control_invalid")
            return
        if not isinstance(value, dict):
            await self.fail("caption_control_invalid")
            return
        if value.get("type") == "stop" and self.upstream and not self.ended:
            self.ended = True
            try:
                await self.upstream.send(json.dumps({"type": "endStream"}))
            except ConnectionClosed:
                await self.fail("transcription_unavailable")
                return
            if self.timer:
                self.timer.cancel()
            self.timer = asyncio.create_task(self.expire(30))
            return
        if value.get("type") != "start" or self.upstream:
            await self.fail("caption_control_invalid")
            return
        if value.get("locale") not in ["es-EC", "en-US"]:
            await self.fail("caption_language_unsupported")
            return
        if (
            value.get("synthetic") is not True
            or os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") != "1"
        ):
            await self.fail("privacy_review_required")
            return
        key = os.environ.get("MODEL_API_KEY", "")
        if os.environ.get("AINGEL_AI_MODE") != "meta" or not key:
            await self.fail("meta_not_configured")
            return
        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.expire(40))
        try:
            self.upstream = await connect(
                "wss://api.meta.ai/v1/asr/realtime",
                open_timeout=15,
                max_size=65536,
                max_queue=8,
            )
            await self.upstream.send(
                json.dumps(
                    {
                        "authorization": {"accessToken": f"Bearer {key}"},
                        "audioEncoding": "PCM_24KHZ",
                        "model": "muse-voice-transcribe-1.0",
                        "mode": "ENDPOINTING",
                        "partialMode": "CUMULATIVE",
                        "languageBias": [
                            "Spanish" if value["locale"] == "es-EC" else "English"
                        ],
                        "emitAudioProgress": False,
                    }
                )
            )
            ack = json.loads(await asyncio.wait_for(self.upstream.recv(), 15))
            if not isinstance(ack, dict) or "sessionId" not in ack:
                await self.fail("transcription_unavailable")
                return
        except (OSError, ValueError, TimeoutError, WebSocketException):
            await self.fail("transcription_unavailable")
            return
        if self.timer:
            self.timer.cancel()
        self.timer = asyncio.create_task(self.expire(600))
        self.started = time.monotonic()
        await self.send(
            text_data=json.dumps(
                {
                    "type": "ready",
                    "model": "muse-voice-transcribe-1.0",
                    "sample_rate": 24000,
                }
            )
        )
        self.receiver = asyncio.create_task(self.drain())

    async def drain(self):
        try:
            async for raw in self.upstream:
                if not isinstance(raw, str):
                    continue
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "error":
                    await self.fail("transcription_unavailable")
                    return
                if kind in {
                    "speechStart",
                    "transcript",
                    "speechEnd",
                    "speechComplete",
                    "speaker",
                }:
                    safe = {
                        k: v
                        for k, v in event.items()
                        if k
                        in {
                            "type",
                            "turnId",
                            "transcript",
                            "final",
                            "label",
                            "audioProcessedMs",
                        }
                    }
                    if len(str(safe.get("transcript", ""))) > 10000:
                        await self.fail("transcript_too_large")
                        return
                    await self.send(text_data=json.dumps(safe))
            await self.send(text_data=json.dumps({"type": "closed"}))
            await self.close(code=1000)
        except (ConnectionClosed, ValueError, TypeError, AttributeError):
            await self.fail("transcription_unavailable")

    async def disconnect(self, close_code):
        for task in [self.timer, self.receiver]:
            if task and task is not asyncio.current_task():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if self.upstream:
            await self.upstream.close()
        if self.lease:
            await cache.adelete(self.lease_key)
