"""Server-controlled synthetic material: the only content that may reach Meta without the person's authorization for
real data.

A client saying that something is synthetic proves nothing: a typed question, a photo, a clip or microphone audio
can hold anyone's private data. So a request without that authorization may only name a fixture defined here. The
server builds the content itself, with a fictitious profile, and never reads the person's profile (name,
preferences, support needs, allergies, notes, memories, history, locale). The old `synthetic` declaration is refused,
and so is free content sent next to a fixture, before any provider request is built.

Every function that calls Meta also receives the basis the view decided (FIXTURE or REAL) and refuses without one.
"""

import io
import os
import tempfile
from pathlib import Path

from rest_framework.decorators import api_view
from rest_framework.response import Response

from .persona import profile_preferences

FIXTURE = "synthetic_fixture"
REAL = "authorized_real"
LOCALES = ("es-EC", "en-US")

# A fictitious adult with the default style: not anyone's profile.
FICTIONAL_PREFERENCES = profile_preferences({})

QUESTIONS = {
    "greeting": {"es-EC": "Hola, ¿cómo estás hoy?", "en-US": "Hello, how are you today?"},
    "capabilities": {"es-EC": "¿En qué me puedes ayudar en casa?", "en-US": "How can you help me at home?"},
    "hydration": {
        "es-EC": "¿Por qué es importante tomar agua durante el día?",
        "en-US": "Why is it important to drink water during the day?",
    },
    "morning": {
        "es-EC": "Dame una idea sencilla para organizar la mañana.",
        "en-US": "Give me one simple idea to organize the morning.",
    },
}
IMAGES = {"shapes": {"es-EC": "Figuras: cuadrado azul y círculo rojo", "en-US": "Shapes: blue square and red circle"}}
# Find-object fixtures: the shapes image and an object name fixed here (the segmentation prompt is English).
OBJECTS = {
    "blue_square": {"es-EC": "Cuadrado azul", "en-US": "Blue square", "prompt": "blue square"},
    "red_circle": {"es-EC": "Círculo rojo", "en-US": "Red circle", "prompt": "red circle"},
}
CLIPS = {"moving_square": {"es-EC": "Un cuadrado azul cruza la mesa", "en-US": "A blue square crosses the table"}}
CATALOG = {"question": QUESTIONS, "image": IMAGES, "object": OBJECTS, "clip": CLIPS}


def enabled():
    """Fixtures are the synthetic-test mode of the server (AINGEL_SYNTHETIC_TESTS_ONLY=1)."""
    return os.environ.get("AINGEL_SYNTHETIC_TESTS_ONLY", "1") == "1"


def require_basis(basis):
    """True only for a basis decided by a view; provider calls check it before building any payload."""
    return basis in (FIXTURE, REAL)


def route(data, kind, real, content):
    """How a request may proceed: ("fixture", id), ("real", None), ("mock", None) or (None, error code).

    [real]: the person's own authorization for this kind of data (care.consent), already checked by the caller.
    [content]: request fields that carry free content or personal context; none may accompany a fixture.
    Without a fixture or that authorization, free content only reaches the local test mode, never Meta.
    """
    if "synthetic" in data:
        return None, "synthetic_fixture_required"
    fixture = data.get("fixture")
    if fixture is not None:
        if not isinstance(fixture, str) or fixture not in CATALOG[kind]:
            return None, "synthetic_fixture_invalid"
        if not enabled():
            return None, "synthetic_tests_disabled"
        if any(field in data for field in content):
            return None, "synthetic_fixture_only"
        return "fixture", fixture
    if real:
        return "real", None
    if os.environ.get("AINGEL_AI_MODE", "mock") == "meta":
        return None, "privacy_review_required"
    return "mock", None


def locale(data):
    """The fixture's language, chosen in the request (never the profile's)."""
    value = data.get("locale", "es-EC")
    return value if value in LOCALES else None


def question(fixture, language):
    return QUESTIONS[fixture][language]


def shapes_image():
    """A blue square on the left and a red circle on the right, on a light background (JPEG)."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (640, 480), (236, 236, 232))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 170, 230, 310), fill=(30, 80, 200))
    draw.ellipse((410, 170, 550, 310), fill=(210, 40, 40))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def moving_square_clip(seconds=6, fps=10):
    """An MP4: a still table for one second, then a blue square enters from the left and crosses it."""
    import cv2
    import numpy as np

    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "fixture.mp4")
        writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (480, 320))
        for i in range(seconds * fps):
            frame = np.full((320, 480, 3), 230, np.uint8)
            cv2.rectangle(frame, (0, 220), (480, 235), (120, 120, 120), -1)
            if i >= fps:
                x = -60 + (i - fps) * 9
                cv2.rectangle(frame, (x, 150), (x + 60, 210), (200, 80, 20), -1)
            writer.write(frame)
        writer.release()
        return Path(path).read_bytes()


def image(fixture):
    return {"shapes": shapes_image}[fixture]()


def clip(fixture):
    return {"moving_square": moving_square_clip}[fixture]()


@api_view(["GET"])
def catalog(request):
    """What a client may offer in synthetic-test mode; the server keeps the content."""
    def items(entries):
        return [{"id": key, **{loc: value[loc] for loc in LOCALES}} for key, value in entries.items()]

    return Response({
        "enabled": enabled(),
        "questions": items(QUESTIONS),
        "images": items(IMAGES),
        "objects": items(OBJECTS),
        "clips": items(CLIPS),
        "captions": False,  # no server-held synthetic speech: live captions need the person's authorization
    })
