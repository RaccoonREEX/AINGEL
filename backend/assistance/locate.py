import base64
import io
import json
import logging
import os
import time

import httpx
from meta_sam_parser import (
    CompletedOutcome,
    InvalidSegmentationMaskError,
    image_segmentation_format,
    decode_mask_to_raster,
)
from PIL import Image

from .scene import SceneUnavailable

log = logging.getLogger(__name__)


def parse_segmentation(text, image_size):
    parser = image_segmentation_format().create_parser()
    parser.push(text)
    parsed = parser.finish(CompletedOutcome()).result
    if parsed.diagnostics:
        raise SceneUnavailable("sam_output_invalid")
    width, height = image_size
    boxes = {x.object_id: x for x in parsed.records if x.kind == "box"}
    masks = {x.object_id: x for x in parsed.records if x.kind == "mask"}
    if len(boxes) > 20:
        raise SceneUnavailable("sam_too_many_matches")
    results = []
    for ident, box in boxes.items():
        if not (
            0 <= box.left < box.right <= width and 0 <= box.top < box.bottom <= height
        ):
            raise SceneUnavailable("sam_output_invalid")
        mask = masks.get(ident)
        if mask is None or mask.mask.width * mask.mask.height > 3_000_000:
            raise SceneUnavailable("sam_output_invalid")
        raster = decode_mask_to_raster(mask.mask)
        alpha = Image.frombytes(
            "L",
            (mask.mask.width, mask.mask.height),
            bytes(110 if v else 0 for v in raster),
        )
        overlay = Image.new("RGBA", alpha.size, (18, 84, 184, 0))
        overlay.putalpha(alpha)
        buffer = io.BytesIO()
        overlay.save(buffer, format="PNG")
        center = (box.left + box.right) / 2 / width
        results.append(
            {
                "id": ident,
                "box": [
                    box.left / width,
                    box.top / height,
                    box.right / width,
                    box.bottom / height,
                ],
                "confidence": box.confidence,
                "horizontal": (
                    "left" if center < 0.4 else "right" if center > 0.6 else "center"
                ),
                "mask_png": "data:image/png;base64,"
                + base64.b64encode(buffer.getvalue()).decode("ascii"),
            }
        )
    if text.strip() and not results:
        raise SceneUnavailable("sam_output_invalid")
    return results


def locate_object(image: bytes, prompt: str, allowed: bool):
    mode = os.environ.get("AINGEL_AI_MODE", "mock")
    if mode == "mock":
        return {
            "mode": "mock",
            "model": None,
            "matches": [],
            "latency_ms": None,
            "analyzed": False,
        }
    if mode != "meta":
        raise SceneUnavailable("ai_mode_invalid")
    key = os.environ.get("MODEL_API_KEY", "").strip()
    if not key:
        raise SceneUnavailable("meta_not_configured")
    if not allowed:
        raise SceneUnavailable("privacy_review_required")
    with Image.open(io.BytesIO(image)) as source:
        size = source.size
    payload = {
        "model": "sam-3.1",
        "store": False,
        "metadata": {"include_confidence": "true", "mask_encoding": "one_bit"},
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
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
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            with client.stream(
                "POST",
                "https://api.meta.ai/v1/responses",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            ) as response:
                response.raise_for_status()
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 4 * 1024 * 1024:
                        raise SceneUnavailable("sam_output_too_large")
        data = json.loads(raw)
        if data.get("status") != "completed":
            raise SceneUnavailable("sam_incomplete")
        text = "\n".join(
            part["text"]
            for item in data.get("output", [])
            if item.get("type") == "message"
            for part in item.get("content", [])
            if part.get("type") == "output_text"
        )
        matches = parse_segmentation(text, size)
    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        InvalidSegmentationMaskError,
    ) as error:
        # Only the failure kind is logged: never the image, the prompt or the model output.
        log.warning("sam_unavailable: %s", type(error).__name__)
        raise SceneUnavailable("sam_unavailable") from None
    except SceneUnavailable as error:
        log.warning("locate failed: %s", error)
        raise
    return {
        "mode": "meta",
        "model": "sam-3.1",
        "matches": matches,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "analyzed": True,
    }
