"""What kind of image Meta received (photograph, drawing, illustration…) is decided from the image itself, apart from
what the person asks (persona «content_type», «drawings», «faces»; assistance.vision and assistance.scene).

These tests check, through the real endpoints with Meta intercepted at the HTTP client, the instructions AINGEL
sends. They do NOT show that Meta tells photographs from drawings correctly: that needs real images with permission."""

import io
import os
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

from . import persona, vision
from .meta_quota import bind_account
from .test_vision import FIXTURES, Provider

PUBLIC = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1",
          "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
CONTENT_TYPE = "CONTENT TYPE."
DRAWINGS = "DRAWINGS."
FACES = "FACES."
REPRESENTED_FIRST = "describe what it represents before how it is drawn"


def picture(name="imagen.png"):
    """A synthetic stand-in (the model is simulated: only the instructions are under test)."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (480, 360), (235, 235, 230))
    image.paste((40, 40, 40), (120, 80, 360, 280))
    image.save(buffer, "PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), "image/png")


class ContentTypeRulesTests(TestCase):
    def test_the_kind_of_image_is_decided_from_the_image_not_the_question_or_source(self):
        rule = persona.POLICIES["content_type"]
        self.assertIn("decide from the image itself, never from the question's wording nor from where it came from", rule)
        for kind in ("a photograph", "a drawing or sketch", "a digital illustration (even a realistic one)", "a painting",
                     "a mixed image", "a photograph of a sheet with a drawing on it (its main content is the drawing)",
                     "a chart, diagram or document", "a kind you cannot tell with certainty"):
            self.assertIn(kind, rule)
        # Every vision task and the Android scene carry it.
        self.assertIn("content_type", persona.VISION_POLICIES)
        self.assertIn(CONTENT_TYPE, persona.VISION_RULES)

    def test_drawings_tell_what_is_represented_before_the_technique(self):
        rule = persona.POLICIES["drawings"]
        represented = rule.index("First, what is represented")
        technique = rule.index("Then, how it is drawn")
        self.assertLess(represented, technique)
        for part in ("its orientation (front, left or right profile, three-quarter, back view)", "proportions between them"):
            self.assertLess(rule.index(part), technique)
        for part in ("stroke thickness", "continuous, broken, repeated or overlapping strokes", "shading, filling and textures"):
            self.assertGreater(rule.index(part), technique)
        self.assertIn("without labels such as «Capa A»", rule)

    def test_intent_is_still_read_from_the_question_but_does_not_fix_the_image_kind(self):
        self.assertEqual(vision.classify("Describe este dibujo")[1], "drawing")
        self.assertEqual(vision.classify("¿Cómo son los trazos?")[1], "drawing")
        self.assertEqual(vision.classify("Describe la imagen")[1], "general")
        self.assertIn("confirm from the image what kind it is", vision.TASK_FOCUS["drawing"])


@patch.dict(os.environ, PUBLIC)
class ContentTypePromptTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="tipo-de-imagen"))
        self.profile = authorize(Profile.objects.create(owner=self.owner, display_name="Tipo"),
                                 camera_local=True, meta_photos=True, meta_screen=True)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.provider = Provider("El dibujo representa un perro sentado de perfil hacia la derecha.")
        self.http = patch("assistance.vision.httpx.Client", self.provider)
        self.http.start()

    def tearDown(self):
        self.http.stop()
        bind_account(None)

    def describe(self, question="", **values):
        data = {"locale": "es-EC", "image": picture(), "profile": str(self.profile.pk), **values}
        if question:
            data["question"] = question
        return self.client.post("/api/v1/vision/", data, format="multipart")

    def follow(self, session, question, **values):
        return self.client.post("/api/v1/vision/", {"locale": "es-EC", "session": session, "question": question, **values}, format="multipart")

    def prompt(self, index=-1):
        return self.provider.prompt(index)

    def test_01_photo_of_a_person_gets_no_stroke_vocabulary(self):
        response = self.describe("¿Cómo se ve la persona de la foto?")
        self.assertEqual((response.status_code, response.data["task"]), (200, "face"))
        prompt = self.prompt()
        self.assertIn(CONTENT_TYPE, prompt)
        self.assertIn("For a PHOTOGRAPH, describe the objects, people and features you observe, and never speak of lines, "
                      "strokes or shading as if the photo were drawn", prompt)
        self.assertIn("PEOPLE AND EXPRESSIONS.", prompt)  # the expression-first improvement is kept

    def test_02_a_face_in_profile_never_gets_its_hidden_eye_or_ear(self):
        self.describe("Describe su perfil")
        prompt = self.prompt()
        self.assertIn("say the head's orientation (facing forward, left or right profile, three-quarter or from behind)", prompt)
        self.assertIn("in a profile one eye or one ear may be hidden, and is never described as seen", prompt)
        self.assertIn("describe the profile of the forehead, nose, lips, chin and jaw", prompt)

    def test_03_a_drawn_animal_is_named_before_its_strokes(self):
        response = self.describe("Describe este dibujo")
        self.assertEqual((response.status_code, response.data["task"]), (200, "drawing"))
        prompt = self.prompt()
        self.assertIn(REPRESENTED_FIRST, prompt)
        self.assertIn("Never replace a recognizable figure with vague phrases such as «hay trazos en una hoja» or «se observan "
                      "numerosos trazos»", prompt)
        self.assertLess(prompt.index(CONTENT_TYPE), prompt.index(DRAWINGS))

    def test_04_a_drawn_human_figure_has_represented_features_not_a_real_person(self):
        self.describe("Describe el dibujo de esta persona")
        prompt = self.prompt()
        self.assertIn(FACES, prompt)
        self.assertIn("In a drawn or painted portrait these are represented features, not those of a real person", prompt)
        self.assertIn("represented expressions and gestures when relevant", prompt)

    def test_05_a_photo_of_a_sheet_with_a_drawing_is_about_the_drawing(self):
        self.describe("Describe la imagen")  # from the camera: still not assumed to be a photograph
        self.assertIn("a photograph of a sheet with a drawing on it (its main content is the drawing)", self.prompt())

    def test_06_a_realistic_digital_illustration_is_not_taken_for_a_photo(self):
        self.describe()
        prompt = self.prompt()
        self.assertIn("a digital illustration (even a realistic one)", prompt)
        self.assertIn("never from the question's wording nor from where it came from", prompt)

    def test_07_an_ambiguous_image_is_described_before_any_reading(self):
        self.describe()
        prompt = self.prompt()
        self.assertIn("a kind you cannot tell with certainty, which you then say", prompt)
        self.assertIn("If the figure is ambiguous, describe what is observable first and offer the possible readings "
                      "with caution and their evidence", prompt)

    def test_08_overlapping_lines_are_technique_never_anatomy(self):
        self.describe("Describe el dibujo")
        prompt = self.prompt()
        self.assertIn("continuous, broken, repeated or overlapping strokes", prompt)
        self.assertIn("Never take a construction line, shading or contour for a real anatomical feature", prompt)
        self.assertIn("Never attribute personality, illness, psychological state or intentions to the author", prompt)

    def test_09_asking_about_the_strokes_after_the_figure_keeps_the_drawing_rules(self):
        session = self.describe("Describe este dibujo").data["session"]
        response = self.follow(session, "¿Cómo son los trazos?")
        self.assertEqual((response.status_code, response.data["task"]), (200, "drawing"))
        prompt = self.prompt()
        self.assertIn(DRAWINGS, prompt)
        self.assertIn("Earlier about this same image the person asked «Describe este dibujo»", prompt)

    def test_10_asking_about_the_face_after_a_drawn_portrait(self):
        session = self.describe("Describe este retrato dibujado").data["session"]
        response = self.follow(session, "¿Y su cara?")
        self.assertEqual((response.status_code, response.data["task"]), (200, "drawing"))  # still a drawing
        prompt = self.prompt()
        for rule in (DRAWINGS, FACES, "PEOPLE AND EXPRESSIONS.", "In a drawn or painted portrait these are represented features"):
            self.assertIn(rule, prompt)

    def test_11_screen_media_is_kept(self):
        response = self.describe("Describe el dibujo que tengo abierto", source_kind="screen")
        self.assertEqual(response.status_code, 200, response.data)
        prompt = self.prompt()
        self.assertIn("SCREEN CONTENT.", prompt)
        self.assertIn(CONTENT_TYPE, prompt)
        self.assertIn(DRAWINGS, prompt)
        self.assertNotIn("name the application or window", prompt)

    def test_deep_keeps_the_kind_and_the_two_layers_in_every_step(self):
        response = self.describe("Describe este dibujo a detalle")
        self.assertEqual((response.status_code, response.data["steps"]), (200, 3), response.data)
        notes = sorted(self.provider.sent[:2], key=lambda payload: len(payload["input"][0]["content"]))
        self.assertIn(vision.CONTENT_NOTES, notes[0]["instructions"])
        self.assertIn(vision.CONTENT_CUES, notes[1]["instructions"])
        self.assertIn(vision.CONTENT_SYNTHESIS.strip(), self.prompt(2))
        for payload in self.provider.sent:
            self.assertIn(CONTENT_TYPE, payload["instructions"])
            self.assertIn(DRAWINGS, payload["instructions"])
        # Same depth as before: no tokens saved on deep descriptions.
        self.assertEqual((self.provider.sent[2]["reasoning"]["effort"], self.provider.sent[2]["max_output_tokens"]), ("high", 12000))

    def test_13_consent_revocation_and_image_protection_continue(self):
        decide(self.profile, self.owner, "meta_photos", "decline")
        self.assertEqual(self.describe("Describe este dibujo").data["error"], "privacy_review_required")
        self.assertEqual(self.provider.sent, [])
        decide(self.profile, self.owner, "meta_photos", "grant")
        session = self.describe("Describe este dibujo").data["session"]
        self.assertNotIn(b"perro sentado", cache.get(vision._key(session)))  # encrypted
        decide(self.profile, self.owner, "meta_photos", "revoke")
        self.assertIn(self.follow(session, "¿Cómo son los trazos?").status_code, (403, 409))
        self.assertEqual(self.follow(session, "¿Cómo son los trazos?").data["error"], "visual_session_expired")
        self.assertEqual(len(self.provider.sent), 1)


class ClientCompatibilityTests(TestCase):
    """12: web and Desktop use vision/ (above); Android also uses scene/ for «Ver y describir»."""

    @patch.dict(os.environ, FIXTURES)
    def test_server_fixtures_still_answer_with_the_same_fields(self):
        cache.clear()
        user = adult(get_user_model().objects.create_user(username="tipo-compat"))
        client = APIClient()
        client.force_authenticate(user)
        with patch("assistance.vision.httpx.Client", Provider("El dibujo representa un perro.")):
            for fixture in ("drawing_dog", "drawing_ambiguous", "face_drawn", "document_page", "screen_desktop"):
                source = "screen" if fixture == "screen_desktop" else "camera"
                response = client.post("/api/v1/vision/", {"locale": "es-EC", "fixture": fixture, "source_kind": source}, format="multipart")
                self.assertEqual(response.status_code, 200, (fixture, response.data))
                self.assertTrue({"text", "paragraphs", "task", "level", "session", "mode"} <= set(response.data), fixture)
        bind_account(None)

    @patch.dict(os.environ, PUBLIC)
    def test_android_scene_carries_the_content_type_rule(self):
        cache.clear()
        owner = adult(get_user_model().objects.create_user(username="tipo-escena"))
        profile = authorize(Profile.objects.create(owner=owner, display_name="Escena"), camera_local=True, meta_photos=True)
        client = APIClient()
        client.force_authenticate(owner)
        with patch("assistance.scene.httpx.Client") as http:
            reply = http.return_value.__enter__.return_value.post.return_value
            reply.json.return_value = {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "El dibujo representa un perro sentado."}]}]}
            response = client.post("/api/v1/scene/", {"locale": "es-EC", "image": picture(), "profile": str(profile.pk)}, format="multipart")
            self.assertEqual(response.status_code, 200, response.data)
            instruction = http.return_value.__enter__.return_value.post.call_args.kwargs["json"]["input"][0]["content"][0]["text"]
        self.assertIn("Scene description from one camera image", instruction)
        self.assertIn(CONTENT_TYPE, instruction)
        self.assertIn("PEOPLE AND EXPRESSIONS.", instruction)
        bind_account(None)
