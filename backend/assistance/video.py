"""Experimental continuous vision with short MP4 clips (behind AINGEL_VIDEO_CLIPS=1, off by default).

The phone keeps a bounded ring of encoded camera frames and sends a clip of ~6 s every ~4 s (2 s overlap). This
endpoint checks the clip is a real MP4 with a video track, sends it to Muse Spark as `input_video` and returns only
what changed since the previous clips, each event marked observed / likely / uncertain.

What it is not: Meta's API takes complete clips per request (no bidirectional video streaming), so latency is clip
length + upload + inference. Nothing is stored: the clip is read in memory (MemoryClipHandler), sent inline by default
(no file left at Meta); the optional Files API transport (AINGEL_VIDEO_TRANSPORT=files) uploads with an expiry and
deletes the file right after. Real clips of people also need AINGEL_VIDEO_REAL=1 (default 0) on top of the person's
«meta_video» grant, while Meta's free-credit content terms remain unreconciled. Synthetic tests name a server fixture
(assistance.synthetic): the server generates the clip and no uploaded clip is sent.
"""

import base64
import json
import os
import struct
import time

import httpx
from django.core.cache import cache
from django.core.files.uploadhandler import MemoryFileUploadHandler
from rest_framework import serializers
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from care.consent import meta_account_denial, meta_allowed, still_current
from care.permissions import access, audit

from . import synthetic
from .meta_quota import MetaQuotaError, reserve_meta_call
from .persona import VISION_RULES, instructions as persona_instructions, profile_preferences, vision_guard

MAX_CLIP_BYTES = 8 * 1024 * 1024
MIN_SECONDS, MAX_SECONDS = 1.0, 10.0
EVENT_TTL = 60          # seconds an event stays in the short temporal context (and is not repeated)
CONTEXT_EVENTS = 8      # bounded context sent with each clip
KINDS = ("appeared", "disappeared", "entered", "left", "placed", "picked_up", "opened", "closed", "moved", "other")
CERTAINTY = ("observed", "likely", "uncertain")


def enabled():
    return os.environ.get("AINGEL_VIDEO_CLIPS", "0") == "1"


class VideoRate(ScopedRateThrottle):
    scope = "video"


class MemoryClipHandler(MemoryFileUploadHandler):
    """Keeps the clip in memory whatever Django's FILE_UPLOAD_MAX_MEMORY_SIZE: no temporary file on disk."""

    def handle_raw_input(self, input_data, META, content_length, boundary, encoding=None):
        self.activated = content_length <= MAX_CLIP_BYTES + 65536


# --- MP4 checks (no decoder needed) -------------------------------------------------------------------------------

def _boxes(data, start=0, end=None):
    end = len(data) if end is None else end
    offset = start
    while offset + 8 <= end:
        size, kind = struct.unpack(">I4s", data[offset:offset + 8])
        header = 8
        if size == 1 and offset + 16 <= end:
            size = struct.unpack(">Q", data[offset + 8:offset + 16])[0]
            header = 16
        elif size == 0:
            size = end - offset
        if size < header or offset + size > end:
            return
        yield kind.decode("latin-1"), offset + header, offset + size
        offset += size


def mp4_info(data):
    """{"seconds", "video"} for a well-formed MP4, or None. Reads ftyp/moov/mvhd/trak/hdlr boxes only."""
    top = {kind: (a, b) for kind, a, b in _boxes(data)}
    if "ftyp" not in top or "moov" not in top:
        return None
    seconds, video = None, False
    moov_a, moov_b = top["moov"]
    for kind, a, b in _boxes(data, moov_a, moov_b):
        if kind == "mvhd" and b - a >= 20:
            version = data[a]
            if version == 1 and b - a >= 32:
                timescale, duration = struct.unpack(">IQ", data[a + 20:a + 32])
            else:
                timescale, duration = struct.unpack(">II", data[a + 12:a + 20])
            seconds = duration / timescale if timescale else None
        elif kind == "trak":
            for k2, a2, b2 in _boxes(data, a, b):
                if k2 == "mdia":
                    for k3, a3, b3 in _boxes(data, a2, b2):
                        if k3 == "hdlr" and b3 - a3 >= 12 and data[a3 + 8:a3 + 12] == b"vide":
                            video = True
    if seconds is None:
        return None
    return {"seconds": round(seconds, 2), "video": video}


# --- Short temporal context (per account and watching session, expiring) ----------------------------------------

def _key(user, session):
    return f"video-context:{user.pk}:{session}"


def recent_events(user, session):
    now = time.time()
    return [e for e in cache.get(_key(user, session), []) if now - e["at"] < EVENT_TTL]


def remember(user, session, events, seq):
    now = time.time()
    kept = recent_events(user, session) + [{**e, "at": now, "seq": seq} for e in events]
    cache.set(_key(user, session), kept[-CONTEXT_EVENTS:], EVENT_TTL)


def new_events(events, previous):
    """Events not already announced in the last EVENT_TTL seconds (same kind and same thing)."""
    seen = {(e["kind"], e["what"].lower()) for e in previous}
    fresh, keys = [], set()
    for event in events:
        key = (event["kind"], event["what"].lower())
        if key not in seen and key not in keys:
            fresh.append(event)
            keys.add(key)
    return fresh


def clean_events(value):
    """Only well-formed events from the model: bounded kinds, certainty and text."""
    events = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        kind, what, certainty = item.get("kind"), item.get("what"), item.get("certainty")
        if kind in KINDS and certainty in CERTAINTY and isinstance(what, str) and 0 < len(what.strip()) <= 80:
            events.append({"kind": kind, "what": what.strip(), "certainty": certainty})
    return events[:6]


CHANGE_TOOL = {
    "type": "function",
    "name": "report_changes",
    "description": "What changed during this clip compared with the previous observations.",
    "parameters": {
        "type": "object",
        "properties": {
            "events": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
                "kind": {"type": "string", "enum": list(KINDS)},
                "what": {"type": "string", "description": "Short noun phrase, e.g. «una taza», «una persona», «la puerta»."},
                "certainty": {"type": "string", "enum": list(CERTAINTY), "description": "observed: clearly seen in the clip; likely: probable interpretation; uncertain: not sure."},
            }, "required": ["kind", "what", "certainty"], "additionalProperties": False}},
            "say": {"type": "string", "description": "One or two short sentences for the person about the new changes only; empty if nothing new."},
        },
        "required": ["events", "say"],
        "additionalProperties": False,
    },
}


def describe_changes(clip, locale, previous, preferences, transport="inline", basis=None):
    """Calls Muse Spark with the clip. Returns (events, say, timings). [basis]: what the view decided."""
    if not synthetic.require_basis(basis):
        raise VideoUnavailable("privacy_review_required")
    key = os.environ.get("MODEL_API_KEY", "").strip()
    if not key:
        raise VideoUnavailable("meta_not_configured")
    task = (
        "Continuous watching with short video clips. You receive one MP4 clip of a few seconds and the recent "
        "observations (with their age in seconds; older ones may no longer be true). Report only what CHANGED during "
        "this clip: something appearing or disappearing, a person entering or leaving the frame, something placed or "
        "picked up, a door opening or closing, something moving. Do not repeat earlier observations; never claim an "
        "event you did not see in this clip. Mark each event observed, likely or uncertain. If nothing changed, "
        "return no events and an empty «say». Always answer by calling report_changes. " + VISION_RULES
    )
    context = json.dumps([{"kind": e["kind"], "what": e["what"], "certainty": e["certainty"], "age_s": int(time.time() - e["at"])} for e in previous], ensure_ascii=False)
    timings = {}
    started = time.monotonic()
    file_id = None
    try:
        # The same global, fail-closed Meta admission as every other call (assistance.meta_quota).
        reserve_meta_call()
    except MetaQuotaError as error:
        raise VideoUnavailable(str(error)) from None
    try:
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            if transport == "files":
                upload_started = time.monotonic()
                upload = client.post("https://api.meta.ai/v1/files", headers={"Authorization": f"Bearer {key}"},
                                     data={"purpose": "user_data", "expires_after[anchor]": "created_at", "expires_after[seconds]": "3600"},
                                     files={"file": ("clip.mp4", clip, "video/mp4")})
                upload.raise_for_status()
                file_id = upload.json()["id"]
                timings["meta_upload_ms"] = round((time.monotonic() - upload_started) * 1000)
                video = {"type": "input_video", "file_id": file_id}
            else:
                video = {"type": "input_video", "video_url": "data:video/mp4;base64," + base64.b64encode(clip).decode("ascii")}
            inference_started = time.monotonic()
            response = client.post("https://api.meta.ai/v1/responses", headers={"Authorization": f"Bearer {key}"}, json={
                "model": "muse-spark-1.3", "store": False, "reasoning": {"effort": "minimal"}, "max_output_tokens": 700,
                "instructions": persona_instructions(locale, preferences, task),
                "tools": [CHANGE_TOOL],  # Meta supports only tool_choice "auto" (30-10-2026)
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": "Recent observations (data): " + context},
                    video,
                ]}],
            })
            timings["meta_inference_ms"] = round((time.monotonic() - inference_started) * 1000)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise VideoUnavailable("meta_unavailable") from None
    finally:
        if file_id:
            # Explicit deletion right after use (the expiry above is the safety net).
            try:
                with httpx.Client(timeout=15) as client:
                    client.delete(f"https://api.meta.ai/v1/files/{file_id}", headers={"Authorization": f"Bearer {key}"})
            except httpx.HTTPError:
                pass
    if data.get("status") != "completed":
        raise VideoUnavailable("meta_incomplete")
    call = next((item for item in data.get("output", []) if item.get("type") == "function_call" and item.get("name") == "report_changes"), None)
    try:
        arguments = json.loads(call["arguments"]) if call else {}
    except (ValueError, TypeError):
        arguments = {}
    timings["meta_total_ms"] = round((time.monotonic() - started) * 1000)
    say = arguments.get("say") if isinstance(arguments.get("say"), str) else ""
    if call is None:
        # The model answered in text instead of the tool: no structured events, the text is what to say.
        say = " ".join(part.get("text", "") for item in data.get("output", []) if item.get("type") == "message"
                       for part in item.get("content", []) if part.get("type") == "output_text")
    return clean_events(arguments.get("events")), say.strip()[:400], timings


class VideoUnavailable(Exception):
    pass


class ClipRequest(serializers.Serializer):
    # A real clip, or the id of a server synthetic fixture (assistance.synthetic); never both.
    clip = serializers.FileField(required=False)
    fixture = serializers.CharField(required=False, max_length=40)
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    profile = serializers.UUIDField(required=False)
    session = serializers.RegexField(r"^[A-Za-z0-9-]{8,64}$")
    seq = serializers.IntegerField(min_value=0, max_value=10**9)


class ClipView(APIView):
    parser_classes = [MultiPartParser]
    throttle_classes = [VideoRate]
    throttle_scope = "video"

    def post(self, request):
        if not enabled():
            return Response({"error": "video_disabled"}, status=404)
        if denial := meta_account_denial(request.user):
            return Response({"error": denial}, status=403)
        # Before the body is parsed: the clip never touches the disk.
        request.upload_handlers = [MemoryClipHandler(request)]
        serializer = ClipRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        received = time.monotonic()
        # Decided before the clip is read: a server fixture, or the person's own grant with real video switched on.
        profile = access(request.user, values["profile"]) if "profile" in values else None
        real = (profile is not None and meta_allowed(profile, "video")
                and os.environ.get("AINGEL_VIDEO_REAL", "0") == "1")
        path, fixture = synthetic.route(request.data, "clip", real, ("clip", "profile"))
        if path is None:
            return Response({"error": fixture}, status=400)
        if path == "fixture":
            clip = synthetic.clip(fixture)
        else:
            if "clip" not in values:
                return Response({"error": "clip_invalid"}, status=400)
            upload = values["clip"]
            if upload.size > MAX_CLIP_BYTES:
                return Response({"error": "clip_too_large"}, status=400)
            clip = upload.read(MAX_CLIP_BYTES + 1)
        info = mp4_info(clip)
        if info is None or not info["video"]:
            return Response({"error": "clip_invalid"}, status=400)
        if not MIN_SECONDS <= info["seconds"] <= MAX_SECONDS:
            return Response({"error": "clip_duration_invalid"}, status=400)

        if os.environ.get("AINGEL_AI_MODE", "mock") == "mock":
            # Test server: the clip was validated, nothing leaves AINGEL.
            return Response({"mode": "mock", "stale": False, "events": [], "say": "", "seconds": info["seconds"],
                             "timings": {"server_ms": round((time.monotonic() - received) * 1000)}})
        if os.environ.get("AINGEL_AI_MODE", "mock") != "meta":
            return Response({"error": "meta_not_configured"}, status=503)
        if path != "real":
            profile = None  # a fixture never uses the person's profile

        # Backpressure: one clip at a time per account; newer clips are dropped by the phone, not queued.
        lease = f"video-busy:{request.user.pk}"
        if not cache.add(lease, True, 90):
            return Response({"error": "video_busy"}, status=429)
        # Cost/quota: bounded clips per account and hour.
        quota_key = f"video-quota:{request.user.pk}:{int(time.time() // 3600)}"
        cache.add(quota_key, 0, 3700)
        if cache.incr(quota_key) > int(os.environ.get("AINGEL_VIDEO_MAX_PER_HOUR", "240")):
            cache.delete(lease)
            return Response({"error": "video_quota_exceeded"}, status=429)
        epoch = profile.consent_epoch if profile is not None else None
        try:
            # Results for a clip older than one already answered are stale: dropped, not announced.
            latest_key = f"video-seq:{request.user.pk}:{values['session']}"
            if values["seq"] <= cache.get(latest_key, -1):
                return Response({"stale": True, "events": [], "say": ""})
            previous = recent_events(request.user, values["session"])
            preferences = (profile_preferences(profile.communication, meta_allowed(profile, "personalization"))
                           if profile is not None else synthetic.FICTIONAL_PREFERENCES)
            try:
                events, say, timings = describe_changes(clip, values["locale"], previous, preferences,
                                                         os.environ.get("AINGEL_VIDEO_TRANSPORT", "inline"),
                                                         basis=synthetic.REAL if path == "real" else synthetic.FIXTURE)
            except VideoUnavailable as error:
                return Response({"error": str(error)}, status=503)
            if values["seq"] <= cache.get(latest_key, -1):
                return Response({"stale": True, "events": [], "say": ""})
            cache.set(latest_key, values["seq"], 3600)
            if profile is not None and real and not still_current(profile, epoch):
                return Response({"error": "consent_changed"}, status=409)
            fresh = new_events(events, previous)
            remember(request.user, values["session"], fresh, values["seq"])
            say = say if fresh else ""
            say, adjusted = vision_guard(say, values["locale"]) if say else ("", False)
        finally:
            cache.delete(lease)
        if profile is not None:
            audit(profile, request.user, "vision.clip")
        timings["server_ms"] = round((time.monotonic() - received) * 1000)
        return Response({
            "mode": "meta", "model": "muse-spark-1.3", "ai_generated": True, "stale": False, "seconds": info["seconds"],
            "events": fresh, "say": say, "safety_adjusted": adjusted, "timings": timings,
        })
