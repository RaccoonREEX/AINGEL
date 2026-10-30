"""Local whole-phrase sign clips. No machine translation or remote video.

A clip is either reviewed by a named person, or an annotated corpus phrase that is explicitly marked
as not independently validated ("corpus_annotation"); the client shows that status with the clip.
"""

from datetime import date
import hashlib
import json
import re
import unicodedata
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponse
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from .permissions import access

MAX_CATALOG_BYTES = 1024 * 1024
MAX_CLIP_BYTES = 20 * 1024 * 1024
MAX_CLIPS = 500
# A generic "other" preference does not identify a language and cannot be
# safely matched to a clip. It remains valid in profile communication settings.
LANGUAGES = {"lsec", "asl"}
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
HASH_PATTERN = re.compile(r"[a-f0-9]{64}\Z")


class SignRate(UserRateThrottle):
    scope = "sign"


class InvalidCatalog(Exception):
    pass


def sign_root():
    return settings.BASE_DIR.parent / ".local" / "signs"


def normalize_phrase(value):
    # Preserve punctuation, accents, negation, and word order. This is not a translation.
    # Only a final full stop is ignored: speech recognisers add or omit it arbitrarily.
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split()).removesuffix(".").rstrip()


def valid_crop(value):
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(type(x) in (int, float) and 0 <= x <= 1 for x in value)
        and value[2] > 0
        and value[3] > 0
        and value[0] + value[2] <= 1
        and value[1] + value[3] <= 1
    )


def valid_text(value, maximum):
    return (
        isinstance(value, str)
        and len(value) <= maximum
        and bool(value.strip())
        and not any(unicodedata.category(c) == "Cc" and not c.isspace() for c in value)
    )


def valid_source_url(value):
    if value is None:
        return True
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(c.isspace() or unicodedata.category(c) == "Cc" for c in value)
        or "\\" in value
    ):
        return False
    try:
        url = urlsplit(value)
        _ = url.port  # Reject malformed and out-of-range ports.
        url.hostname.encode("idna") if url.hostname else None
        return bool(
            url.scheme == "https"
            and url.hostname
            and not url.username
            and not url.password
        )
    except ValueError:
        return False


def load_catalog():
    try:
        with (sign_root() / "catalog.json").open("rb") as stream:
            raw = stream.read(MAX_CATALOG_BYTES + 1)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise InvalidCatalog from exc
    try:
        if len(raw) > MAX_CATALOG_BYTES:
            raise ValueError
        catalog = json.loads(raw)
        if (
            not isinstance(catalog, dict)
            or type(catalog.get("version")) is not int
            or catalog["version"] != 1
        ):
            raise ValueError
        clips = catalog.get("clips")
        if not isinstance(clips, list) or len(clips) > MAX_CLIPS:
            raise ValueError
        ids = set()
        phrases = set()
        for clip in clips:
            if not isinstance(clip, dict):
                raise ValueError
            required = {
                "id",
                "language",
                "text",
                "filename",
                "sha256",
                "reviewed",
                "source",
                "attribution",
                "license",
            }
            if clip.get("reviewed") is True:
                required |= {"reviewer", "reviewed_at"}
                if not valid_text(clip.get("reviewer"), 200):
                    raise ValueError
                date.fromisoformat(clip.get("reviewed_at", ""))
            elif clip.get("reviewed") is False and clip.get("validation") == "corpus_annotation":
                # Corpus label only: allowed, but never presented as reviewed.
                required |= {"validation", "validation_note"}
                if not valid_text(clip.get("validation_note"), 300):
                    raise ValueError
            else:
                raise ValueError
            if not required.issubset(clip) or set(clip) - (required | {"source_url", "crop"}):
                raise ValueError
            if "crop" in clip and not valid_crop(clip["crop"]):
                raise ValueError
            identifier, digest = clip.get("id"), clip.get("sha256")
            if (
                not isinstance(identifier, str)
                or not ID_PATTERN.fullmatch(identifier)
                or identifier in ids
            ):
                raise ValueError
            if not isinstance(digest, str) or not HASH_PATTERN.fullmatch(digest):
                raise ValueError
            if clip.get("filename") != digest + ".mp4":
                raise ValueError
            if clip.get("language") not in LANGUAGES or not valid_text(
                clip.get("text"), 300
            ):
                raise ValueError
            if not all(
                valid_text(clip.get(field), limit)
                for field, limit in (
                    ("source", 300),
                    ("attribution", 500),
                    ("license", 300),
                )
            ):
                raise ValueError
            if not valid_source_url(clip.get("source_url")):
                raise ValueError
            phrase = (clip["language"], normalize_phrase(clip["text"]))
            if not phrase[1] or phrase in phrases:
                raise ValueError
            ids.add(identifier)
            phrases.add(phrase)
        return clips
    except (ValueError, TypeError, UnicodeError, KeyError) as exc:
        raise InvalidCatalog from exc


PUBLIC_FIELDS = ("id", "language", "source", "attribution", "license", "source_url", "crop")


def public_clip(clip):
    data = {key: clip.get(key) for key in PUBLIC_FIELDS}
    data["validation"] = "reviewed" if clip["reviewed"] else clip["validation"]
    data["validation_note"] = clip.get("validation_note")
    return data


def read_clip(clip):
    """Hash the actual bytes returned, keeping them in memory to avoid file races."""
    root = sign_root() / "clips"
    path = root / clip["filename"]
    try:
        if path.is_symlink() or path.resolve(strict=True).parent != root.resolve(
            strict=True
        ):
            raise InvalidCatalog
        with path.open("rb") as stream:
            data = stream.read(MAX_CLIP_BYTES + 1)
    except OSError as exc:
        raise InvalidCatalog from exc
    if len(data) > MAX_CLIP_BYTES or len(data) < 12 or data[4:8] != b"ftyp":
        raise InvalidCatalog
    box_length = int.from_bytes(data[:4], "big")
    if (
        box_length < 8
        or box_length > len(data)
        or hashlib.sha256(data).hexdigest() != clip["sha256"]
    ):
        raise InvalidCatalog
    return data


@api_view(["POST"])
@throttle_classes([SignRate])
def lookup(request, profile_id):
    access(request.user, profile_id)
    data = request.data
    if not isinstance(data, dict) or set(data) != {"text", "language"}:
        return Response({"error": "sign_request_invalid"}, status=400)
    phrase, language = data["text"], data["language"]
    if (
        not valid_text(phrase, 300)
        or not isinstance(language, str)
        or language not in LANGUAGES
    ):
        return Response({"error": "sign_request_invalid"}, status=400)
    try:
        clips = load_catalog()
        clip = next(
            (
                item
                for item in clips
                if item["language"] == language
                and normalize_phrase(item["text"]) == normalize_phrase(phrase)
            ),
            None,
        )
        if clip is None:
            return Response({"available": False})
        read_clip(clip)
    except InvalidCatalog:
        return Response({"error": "sign_catalog_invalid"}, status=503)
    return Response({"available": True, "clip": public_clip(clip)})


@api_view(["GET"])
@throttle_classes([SignRate])
def catalog(request, profile_id):
    """Phrases that can actually be shown, per language, so the screen never implies more coverage."""
    access(request.user, profile_id)
    language = request.query_params.get("language", "")
    if language not in LANGUAGES:
        return Response({"error": "sign_request_invalid"}, status=400)
    try:
        clips = [clip for clip in load_catalog() if clip["language"] == language]
    except InvalidCatalog:
        return Response({"error": "sign_catalog_invalid"}, status=503)
    return Response(
        {"language": language, "phrases": [{**public_clip(c), "text": c["text"]} for c in clips]}
    )


@api_view(["GET"])
@throttle_classes([SignRate])
def clip_content(request, profile_id, clip_id):
    access(request.user, profile_id)
    if not ID_PATTERN.fullmatch(clip_id):
        return Response({"error": "sign_clip_not_found"}, status=404)
    try:
        clips = load_catalog()
        clip = next((item for item in clips if item["id"] == clip_id), None)
        if clip is None:
            return Response({"error": "sign_clip_not_found"}, status=404)
        video = read_clip(clip)
    except InvalidCatalog:
        return Response({"error": "sign_catalog_invalid"}, status=503)
    response = HttpResponse(video, content_type="video/mp4")
    response["Content-Disposition"] = 'inline; filename="aingel-sign.mp4"'
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
