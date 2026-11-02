"""A bounded scene slice. Images are never persisted by this service."""

import base64
import io
import os
import time
import warnings

import httpx

from .persona import VISION_RULES, instructions as persona_instructions, profile_preferences, vision_guard
from PIL import Image, ImageOps, UnidentifiedImageError
from . import usage
from .meta_quota import MetaQuotaError, reserve_meta_call
from .synthetic import require_basis

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 12_000_000


class SceneUnavailable(Exception):
    pass


def normalize_image(upload, side=1600) -> bytes:
    if upload.size > MAX_BYTES:
        raise ValueError("image_too_large")
    raw = upload.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("image_too_large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("image_format_unsupported")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("image_too_large")
                image.load()
                clean = ImageOps.exif_transpose(image).convert("RGB")
                clean.thumbnail((side, side))
                output = io.BytesIO()
                clean.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValueError("image_invalid") from None


def describe_scene(image: bytes, locale: str, allowed, known_person: bool = False, preferences=None) -> dict:
    """[allowed]: the basis the view decided (assistance.synthetic FIXTURE or REAL); anything else sends nothing.
    [known_person]: AINGEL recognized a family member locally; Meta never gets the name, only asked to describe them."""
    mode = os.environ.get("AINGEL_AI_MODE", "mock")
    if mode == "mock":
        # Deliberately describes no objects: the fixture must never look like visual inference.
        text = (
            "Modo de prueba: no se analizó la imagen."
            if locale == "es-EC"
            else "Test mode: the image was not analyzed."
        )
        return {"text": text, "mode": "mock", "model": None, "latency_ms": None}
    if mode != "meta":
        raise SceneUnavailable("ai_mode_invalid")
    key = os.environ.get("MODEL_API_KEY", "").strip()
    if not key:
        raise SceneUnavailable("meta_not_configured")
    if not require_basis(allowed):
        raise SceneUnavailable("privacy_review_required")
    language = "Ecuadorian Spanish" if locale == "es-EC" else "English"
    # Brief, as PEOPLE AND EXPRESSIONS asks for BRIEF: a person's apparent expression and one or two key features.
    task = "Scene description from one photo, at most three short sentences. " + VISION_RULES + (
        " If a person is the main subject, the first sentence gives their apparent expression."
    ) + (
        " The person in front is someone the user knows; the app already says who it is. Without naming or "
        "identifying them, start with that person: their apparent expression, what they are wearing and what they "
        "seem to be doing."
        if known_person else ""
    )
    instruction = persona_instructions(locale, preferences or profile_preferences({}), task)
    payload = {
        "model": "muse-spark-1.3",
        "store": False,
        "reasoning": {"effort": "minimal"},
        "max_output_tokens": 1000,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": instruction},
                    {
                        "type": "input_image",
                        "image_url": "data:image/jpeg;base64,"
                        + base64.b64encode(image).decode("ascii"),
                    },
                ],
            }
        ],
    }
    started = time.monotonic()
    try:
        usage.admit()
        reserve_meta_call()
    except (MetaQuotaError, usage.BudgetExhausted) as error:
        raise SceneUnavailable(str(error)) from None
    try:
        # Fixed destination: no user-provided URLs and no forwarding redirects with credentials.
        with httpx.Client(timeout=45, follow_redirects=False) as client:
            response = client.post(
                "https://api.meta.ai/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        usage.record("scene", "muse-spark-1.3", "minimal", data.get("usage"), round((time.monotonic() - started) * 1000),
                     allowed, data.get("status"))
        if data.get("status") != "completed":
            raise SceneUnavailable("meta_incomplete")
        text = "\n".join(
            part["text"]
            for item in data.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        ).strip()
        if not text:
            raise SceneUnavailable("meta_empty_response")
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
        # Provider bodies can contain private payloads. Never expose or log them here.
        raise SceneUnavailable("meta_unavailable") from None
    # Rule 1 in code: an assurance that a path is clear or safe is replaced, never shown nor spoken.
    text, adjusted = vision_guard(text, locale)
    return {
        "text": text,
        "safety_adjusted": adjusted,
        "ai_generated": True,
        "mode": "meta",
        "model": "muse-spark-1.3",
        "latency_ms": round((time.monotonic() - started) * 1000),
    }
