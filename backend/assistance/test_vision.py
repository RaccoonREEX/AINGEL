"""AINGEL 3.0 deep vision (assistance.vision): levels, tasks, regions, follow-up sessions, consent and usage.

Every request that would reach Meta is intercepted at the HTTP client; nothing leaves the machine.
"""

import base64
import io
import json
import os
import threading
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from care.consent import decide
from care.models import Profile
from care.testing import adult, authorize

from . import synthetic, vision
from .models import MetaUsage
from .persona import POLICIES
from .test_synthetic_isolation import MARKERS, PrivateProfileMixin

FIXTURES = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_REAL_DATA": "0"}
PRIVATE = {
    "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "1",
    "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0",
}
USAGE = {
    "input_tokens": 2000, "input_tokens_details": {"cached_tokens": 0}, "output_tokens": 1000,
    "output_tokens_details": {"reasoning_tokens": 400}, "total_tokens": 3000,
}
MARKDOWN = "## Resumen\n\nVeo un **perro** de dibujo.\n\n- Orejas caídas\n- Cola levantada\n\n| Parte | Color |\n|---|---|\n| Cuerpo | marrón |"


class Provider:
    """Stands in for httpx.Client in assistance.vision; records each payload (calls may come from two threads)."""

    def __init__(self, text=MARKDOWN, status="completed"):
        self.sent, self.lock, self.text, self.status = [], threading.Lock(), text, status

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        with self.lock:
            self.sent.append(json)
        return self

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": self.status, "usage": USAGE,
                "output": [{"type": "message", "content": [{"type": "output_text", "text": self.text}]}]}

    def prompt(self, index=-1):
        """AINGEL's instructions, sent in the request's own field (never in the user's turn)."""
        return self.sent[index]["instructions"]

    def images(self, index=-1):
        return [part["image_url"] for part in self.sent[index]["input"][0]["content"] if part["type"] == "input_image"]


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (200, 120, 40)).save(buffer, "PNG")
    return SimpleUploadedFile("photo.png", buffer.getvalue(), "image/png")


class ClassifyTests(TestCase):
    def test_levels_tasks_and_regions_from_the_question(self):
        self.assertEqual(vision.classify("Descríbeme esta foto a detalle"), ("deep", "general", None))
        self.assertEqual(vision.classify("Explícame el dibujo a fondo"), ("deep", "drawing", None))
        self.assertEqual(vision.classify("¿Qué hay en el fondo?"), ("standard", "general", "background"))
        self.assertEqual(vision.classify("Describe con detalle su rostro"), ("detailed", "face", None))
        self.assertEqual(vision.classify("¿Y sus ojos?")[1], "face")
        self.assertEqual(vision.classify("¿Qué hay arriba a la izquierda?")[2], "top_left")
        self.assertEqual(vision.classify("Lee esta página")[1], "document")
        self.assertEqual(vision.classify("Análisis académico para psicología del dibujo")[1], "academic")
        self.assertEqual(vision.classify("Dime rápido qué ves")[0], "brief")
        self.assertEqual(vision.classify("What does the person look like?")[1], "face")
        self.assertEqual(vision.classify("", "screen")[1], "screen")
        # «caracter» is not «cara»: whole words only.
        self.assertEqual(vision.classify("¿Qué carácter tiene el lugar?")[1], "general")

    def test_explicit_fields_win_and_the_content_type_stays_across_follow_ups(self):
        plan = vision.plan("a detalle", detail_level="brief", visual_task="chart", focus_region="right")
        self.assertEqual(plan, vision.Plan("brief", "chart", "right"))
        self.assertEqual(vision.plan("¿Y los ojos?", previous="drawing").task, "drawing")
        self.assertEqual(vision.plan("¿Qué hay atrás?", previous="face").task, "face")
        self.assertEqual(vision.plan("¿Y su cara?", previous="general").task, "face")

    def test_speech_text_has_no_markdown(self):
        text, paragraphs = vision.speakable(MARKDOWN + "\n\n1. *Primero* la cabeza\n---\n[enlace](https://x.example)")
        for mark in ("#", "**", "|", "- ", "*", "---", "](", "1."):
            self.assertNotIn(mark, text)
        self.assertEqual(paragraphs[0], "Resumen.")
        self.assertIn("Orejas caídas. Cola levantada.", text)
        self.assertIn("Cuerpo, marrón.", text)
        self.assertTrue(text.endswith("enlace"))

    def test_crops_keep_the_source_resolution(self):
        image = synthetic.image("drawing_dog")
        with Image.open(io.BytesIO(vision.crop(image, "top_right"))) as part:
            self.assertEqual(part.size, (440, 330))


class VisionPayloadTests(PrivateProfileMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.make_private_profile()
        self.provider = Provider()
        self.patch = patch("assistance.vision.httpx.Client", self.provider)
        self.patch.start()
        self.env = patch.dict(os.environ, FIXTURES)
        self.env.start()

    def tearDown(self):
        self.patch.stop()
        self.env.stop()

    def post(self, **values):
        return self.client.post("/api/v1/vision/", {"locale": "es-EC", **values}, format="multipart")

    def test_each_level_sets_effort_and_a_budget_that_leaves_room_for_reasoning(self):
        for level, effort, budget in (("brief", "low", 2500), ("standard", "medium", 5000), ("detailed", "high", 10000)):
            response = self.post(fixture="drawing_dog", detail_level=level)
            self.assertEqual(response.status_code, 200, response.data)
            sent = self.provider.sent[-1]
            self.assertEqual((sent["reasoning"], sent["max_output_tokens"]), ({"effort": effort}, budget))
            self.assertEqual((sent["model"], sent["store"]), ("muse-spark-1.3", False))
            self.assertIn(f"Detail level: {level.upper()}", self.provider.prompt())
            self.assertNotEqual(sent["reasoning"]["effort"], "minimal")
        self.assertEqual(len(self.provider.sent), 3)

    def test_deep_runs_overview_and_enlarged_regions_then_a_synthesis(self):
        response = self.post(fixture="drawing_dog", detail_level="deep")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["steps"], 3)
        self.assertEqual(len(self.provider.sent), 3)
        steps = sorted(self.provider.sent[:2], key=lambda payload: len(payload["input"][0]["content"]))
        overview, regions = (payload["input"][0]["content"] for payload in steps)
        self.assertIn("STEP 1 of 3", steps[0]["instructions"])
        self.assertEqual(sum(part["type"] == "input_image" for part in overview), 1)
        self.assertIn("STEP 2 of 3", steps[1]["instructions"])
        self.assertEqual(sum(part["type"] == "input_image" for part in regions), 6)  # whole image + five crops
        final = self.provider.sent[2]
        self.assertIn("STEP 3 of 3", self.provider.prompt(2))
        self.assertIn("Notes 1:", self.provider.prompt(2))
        self.assertEqual((final["reasoning"]["effort"], final["max_output_tokens"]), ("high", 12000))
        for payload in self.provider.sent:
            self.assertEqual(payload["max_output_tokens"] >= 8000, True)

    def test_a_question_asking_for_detail_is_deep_and_the_answer_is_speakable(self):
        # A typed question is free content, so it needs an authorized real image (see VisionConsentTests);
        # here the level is what the classifier makes of the same words.
        self.assertEqual(vision.plan("Descríbelo a detalle").level, "deep")
        response = self.post(fixture="drawing_dog", detail_level="detailed")
        self.assertNotIn("**", response.data["text"])
        self.assertIn("Veo un perro de dibujo.", response.data["paragraphs"])

    def test_task_policies_reach_the_prompt(self):
        self.post(fixture="face_drawn", visual_task="face")
        prompt = self.provider.prompt()
        self.assertIn(POLICIES["faces"], prompt)
        self.assertIn("never infer diagnoses, ethnic origin", prompt)
        self.assertIn("never attribute identity by facial resemblance", prompt)
        self.post(fixture="drawing_dog", visual_task="drawing")
        self.assertIn("say first what it represents", self.provider.prompt())
        self.assertIn("Never answer «hay trazos en una hoja»", self.provider.prompt())
        self.post(fixture="drawing_ambiguous", visual_task="academic")
        prompt = self.provider.prompt()
        self.assertIn("«Observaciones visuales»", prompt)
        self.assertIn("«Interpretaciones teóricas» only if the question asks", prompt)
        self.assertIn("Never diagnose anyone from a drawing", prompt)
        self.post(fixture="document_page", visual_task="document")
        self.assertIn("never invent words", self.provider.prompt())

    def test_focus_region_adds_the_enlarged_crop(self):
        self.post(fixture="drawing_dog", focus_region="top_right")
        images = self.provider.images()
        self.assertEqual(len(images), 2)
        self.assertIn("enlarged crop of the upper-right part", self.provider.prompt())

    def test_fixture_requests_carry_no_private_profile_data_and_refuse_free_text(self):
        for level in vision.LEVELS:
            self.post(fixture="face_drawn", detail_level=level)
        text = json.dumps(self.provider.sent, ensure_ascii=False)
        for marker in MARKERS:
            self.assertNotIn(marker, text)
        count = len(self.provider.sent)
        for extra in ({"question": "ZZQ-CLIENT"}, {"profile": str(self.profile.pk)}, {"image": photo()}):
            response = self.post(fixture="drawing_dog", **extra)
            self.assertEqual(response.data["error"], "synthetic_fixture_only")
        self.assertEqual(len(self.provider.sent), count)

    def test_follow_up_reuses_the_session_image_and_remembers_the_content_type(self):
        first = self.post(fixture="drawing_dog", visual_task="drawing").data
        token = first["session"]
        self.assertEqual(first["session_seconds"], vision.SESSION_SECONDS)
        image = self.provider.images()[0]
        response = self.post(session=token, focus_region="top_right")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.provider.images()[0], image)
        self.assertEqual(response.data["task"], "drawing")
        self.assertIn("Earlier about this same image", self.provider.prompt())
        # Free text never joins a fixture session, and a fixture session never accepts a new picture.
        self.assertEqual(self.post(session=token, question="ZZQ-CLIENT").data["error"], "synthetic_fixture_only")
        self.assertEqual(self.post(session=token, fixture="shapes").data["error"], "visual_session_conflict")

    def test_sessions_belong_to_their_account_and_can_be_closed(self):
        token = self.post(fixture="shapes").data["session"]
        other = APIClient()
        other.force_authenticate(adult(get_user_model().objects.create_user(username="vision-other")))
        response = other.post("/api/v1/vision/", {"locale": "es-EC", "session": token}, format="multipart")
        self.assertEqual((response.status_code, response.data["error"]), (404, "visual_session_expired"))
        self.assertEqual(self.client.delete(f"/api/v1/vision/sessions/{token}/").status_code, 204)
        self.assertEqual(self.post(session=token).data["error"], "visual_session_expired")

    def test_session_is_encrypted_in_the_cache(self):
        token = self.post(fixture="shapes").data["session"]
        sealed = cache.get(vision._key(token))
        self.assertNotIn(b"shapes", sealed)
        self.assertNotIn(token.encode(), sealed)

    def test_usage_is_recorded_without_content_and_the_budget_can_stop_calls(self):
        self.post(fixture="drawing_dog", detail_level="detailed")
        row = MetaUsage.objects.get()
        self.assertEqual((row.feature, row.effort, row.basis, row.status), ("vision_detailed", "high", synthetic.FIXTURE, "completed"))
        self.assertEqual((row.input_tokens, row.output_tokens, row.reasoning_tokens), (2000, 1000, 400))
        self.assertEqual(row.cost_usd, Decimal("0.006750"))  # 2000 × 1.25 + 1000 × 4.25 per million
        self.assertEqual(row.user, self.owner)
        with patch.dict(os.environ, {"AINGEL_META_BUDGET_USD": "0.006"}):
            response = self.post(fixture="drawing_dog")
        self.assertEqual((response.status_code, response.data["error"]), (503, "meta_budget_exhausted"))
        self.assertEqual(len(self.provider.sent), 1)

    def test_an_incomplete_answer_is_not_shown(self):
        self.provider.status = "incomplete"
        response = self.post(fixture="drawing_dog")
        self.assertEqual((response.status_code, response.data["error"]), (503, "meta_incomplete"))
        self.assertEqual(MetaUsage.objects.get().status, "incomplete")  # still billed, so still recorded

    def test_mobility_assurances_are_replaced(self):
        self.provider.text = "El camino está despejado y es seguro."
        response = self.post(fixture="shapes")
        self.assertTrue(response.data["safety_adjusted"])
        self.assertNotIn("es seguro", response.data["text"])


class VisionConsentTests(TestCase):
    """The owner's own photo in the private test, as in assistance.test_private_media."""

    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="vision-owner"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Owner", face_recognition_enabled=True)
        authorize(self.profile, {"camera": True, "microphone": True, "meta_data": True})
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.provider = Provider("Veo una superficie naranja.")
        self.patches = [patch("assistance.vision.httpx.Client", self.provider), patch.dict(os.environ, PRIVATE)]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()

    def post(self, **values):
        return self.client.post("/api/v1/vision/", {"locale": "es-EC", **values}, format="multipart")

    def start(self, question="Descríbeme esta foto a detalle"):
        response = self.post(image=photo(), profile=str(self.profile.pk), private_test=True, question=question)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_a_question_sets_the_level_and_follow_ups_use_the_same_image(self):
        first = self.start()
        self.assertEqual((first["level"], first["steps"]), ("deep", 3))
        image = self.provider.images()[0]
        response = self.post(session=first["session"], question="¿Y qué hay en el fondo?")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.provider.images()[0], image)
        self.assertEqual(response.data["region"], "background")
        prompt = self.provider.prompt()
        self.assertIn("«Descríbeme esta foto a detalle»", prompt)
        self.assertIn("«¿Y qué hay en el fondo?»", prompt)

    def test_without_consent_nothing_is_sent(self):
        decide(self.profile, self.owner, "meta_photos", "revoke")
        response = self.post(image=photo(), profile=str(self.profile.pk), private_test=True, question="¿Qué ves?")
        self.assertEqual(response.data["error"], "privacy_review_required")
        self.assertEqual(self.provider.sent, [])

    def test_revocation_ends_the_session_and_deletes_the_image(self):
        for purpose, error in (("camera_local", "camera_consent_revoked"), ("meta_photos", "consent_changed")):
            authorize(self.profile, {"camera": True, "microphone": True, "meta_data": True})
            token = self.start("¿Qué ves?")["session"]
            sent = len(self.provider.sent)
            decide(self.profile, self.owner, purpose, "revoke")
            response = self.post(session=token, question="¿Y los colores?")
            self.assertEqual(response.data["error"], error, purpose)
            self.assertEqual(len(self.provider.sent), sent)
            self.assertIsNone(cache.get(vision._key(token)))

    def test_revocation_while_meta_looks_drops_the_answer_and_the_session(self):
        token = self.start("¿Qué ves?")["session"]
        original = self.provider.post

        def revoke_then_answer(*args, **kwargs):
            decide(self.profile, self.owner, "meta_photos", "revoke")
            return original(*args, **kwargs)

        with patch.object(self.provider, "post", revoke_then_answer):
            response = self.post(session=token, question="¿Y los colores?")
        self.assertEqual((response.status_code, response.data["error"]), (409, "consent_changed"))
        self.assertIsNone(cache.get(vision._key(token)))

    def test_the_session_image_is_the_normalized_photo(self):
        token = self.start("¿Qué ves?")["session"]
        state = vision.load_session(token, self.owner)
        self.assertEqual(base64.b64decode(state["image"])[:2], b"\xff\xd8")  # JPEG, EXIF-free
        self.assertEqual(state["profile"], str(self.profile.pk))
