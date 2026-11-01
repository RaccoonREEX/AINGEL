import asyncio
import contextlib
import json
import os
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.core.cache import cache
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, WebSocketException

from care.consent import meta_account_denial, meta_allowed, private_media_allowed, still_current
from care.permissions import access
from . import usage
from .meta_quota import MetaQuotaError, reserve_meta_call

VOICE = "muse-voice-transcribe-1.0"
BYTES_PER_SECOND = 48000  # PCM16 mono at 24 kHz, as declared to Meta (audioEncoding)


class CaptionConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def profile_allows(self, profile_id, private_test=False, kind="audio"):
        """[kind]: «audio» for the person's own microphone, «meeting_audio» for the computer's audio (AINGEL Desktop),
        which may hold other people's voices and has its own purpose (care.consent.meta_meeting_audio)."""
        if not isinstance(profile_id, str):
            return False
        try:
            user = self.scope["user"]
            profile = access(user, profile_id)
            allowed = private_media_allowed(profile, user, kind, private_test) or meta_allowed(profile, kind)
            if allowed:
                # Re-checked while streaming: a revocation ends the session (receive).
                self.consent_profile, self.consent_epoch = profile, profile.consent_epoch
            return allowed
        except Exception:
            return False

    async def connect(self):
        self.upstream = None
        self.receiver = None
        self.timer = None
        self.lease = False
        self.ended = False
        self.bytes_sent = 0
        self.bytes_forwarded = 0
        self.billed_kind = None
        self.consent_profile = None
        self.consent_epoch = None
        self.consent_checked = 0.0
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
            if self.consent_profile is not None and time.monotonic() - self.consent_checked > 5:
                self.consent_checked = time.monotonic()
                if not await database_sync_to_async(still_current)(self.consent_profile, self.consent_epoch):
                    await self.fail("consent_changed")
                    return
            try:
                await self.upstream.send(bytes_data)
                self.bytes_forwarded += len(bytes_data)
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
        if denial := await database_sync_to_async(meta_account_denial)(self.scope.get("user")):
            await self.fail(denial)
            return
        # Only the person's own authorization (microphone + voice to Meta). A client calling its audio synthetic proves
        # nothing, and the server holds no synthetic speech to send instead (assistance.synthetic).
        if "synthetic" in value or "fixture" in value:
            await self.fail("synthetic_captions_unavailable")
            return
        source = value.get("source", "microphone")
        if source not in ("microphone", "system"):
            await self.fail("caption_control_invalid")
            return
        kind = "meeting_audio" if source == "system" else "audio"
        if not await self.profile_allows(value.get("profile"), value.get("private_test"), kind):
            await self.fail("privacy_review_required")
            return
        key = os.environ.get("MODEL_API_KEY", "")
        if os.environ.get("AINGEL_AI_MODE") != "meta" or not key:
            await self.fail("meta_not_configured")
            return
        try:
            # Counted for this account (assistance.meta_quota), not only for the platform, and within its budget.
            account = self.scope["user"].pk
            await database_sync_to_async(usage.admit)(account)
            await sync_to_async(lambda: reserve_meta_call(account=account), thread_sensitive=False)()
        except (MetaQuotaError, usage.BudgetExhausted) as error:
            await self.fail(str(error))
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
                        "model": VOICE,
                        "mode": "ENDPOINTING",
                        "partialMode": "CUMULATIVE",
                        "languageBias": [
                            "Spanish" if value["locale"] == "es-EC" else "English"
                        ],
                        "emitAudioProgress": False,
                    }
                )
            )
            # From here Meta may bill the audio sent, so the session is recorded when it ends (disconnect).
            self.billed_kind = kind
            self.billed_started = time.monotonic()
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
                    "model": VOICE,
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
        if self.billed_kind:
            await self.bill()
        if self.lease:
            await cache.adelete(self.lease_key)

    async def bill(self):
        """One ledger row per stream, for the account of this connection: the seconds of audio AINGEL forwarded to
        Meta (Meta bills audio processed in whole seconds, rounded down). No audio or transcript is kept."""
        kind, self.billed_kind = self.billed_kind, None
        await database_sync_to_async(usage.record)(
            "captions_system" if kind == "meeting_audio" else "captions", VOICE, "", None,
            round((time.monotonic() - self.billed_started) * 1000), kind, "completed" if self.ended else "closed",
            self.scope["user"], audio_seconds=self.bytes_forwarded // BYTES_PER_SECOND,
        )
