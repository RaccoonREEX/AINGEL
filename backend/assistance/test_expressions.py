"""People and their apparent expressions (persona POLICIES «expressions», assistance.vision and assistance.scene).

These tests check what AINGEL instructs Meta, through the real endpoints, with Meta intercepted at the HTTP client.
They show that the priorities reach Meta at every step; they are NOT evidence of how accurately Meta reads
expressions, which only a real evaluation with consented photos can show."""

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
from care.faces import recognition_enabled
from care.models import Profile
from care.testing import adult, authorize

from . import persona, vision
from .meta_quota import MetaQuotaError, bind_account
from .test_vision import Provider

PUBLIC = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1",
          "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
EXPRESSIONS = "PEOPLE AND EXPRESSIONS."
SAD = ("El hombre parece triste o afligido. Sus cejas están elevadas hacia el centro y las comisuras de los labios "
       "apuntan hacia abajo.\n\nTiene cabello oscuro, corto y ondulado, y barba corta.")


def portrait():
    """A synthetic stand-in for a portrait (the model is simulated: only the instructions are under test)."""
    buffer = io.BytesIO()
    image = Image.new("RGB", (480, 640), (200, 190, 180))
    image.paste((120, 90, 70), (140, 120, 340, 380))
    image.save(buffer, "PNG")
    return SimpleUploadedFile("retrato.png", buffer.getvalue(), "image/png")


class ExpressionRulesTests(TestCase):
    """The shared rules themselves (persona.POLICIES)."""

    def test_expression_comes_first_then_cues_then_appearance_then_context(self):
        text = persona.POLICIES["expressions"]
        order = [text.index(part) for part in ("(1) Their apparent facial expression", "(2) Briefly, the visible cues",
                                               "(3) Their appearance", "(4) The context")]
        self.assertEqual(order, sorted(order))
        for example in ("«Parece triste»", "«Su expresión transmite alegría»", "«Tiene un gesto de preocupación»"):
            self.assertIn(example, text)

    def test_no_confirmed_emotions_diagnoses_intentions_or_identity(self):
        rules = persona.policies("expressions", "faces", "people")
        self.assertIn("never as a fact about their inner state", rules)
        self.assertIn("never state confirmed emotions, mental states, intentions, diagnoses or personality", rules)
        self.assertIn("never infer diagnoses, ethnic origin or other sensitive attributes", rules)
        self.assertIn("never attribute identity by facial resemblance", rules)
        self.assertIn("Never identify strangers nor infer their identity, health or intentions", rules)
        # The old blanket ban on describing expressions is gone; the ban on confirmed feelings stays.
        self.assertNotIn("infer their identity, emotions", rules)

    def test_the_questions_people_ask_are_about_a_person(self):
        for question, level in (("¿Cómo se ve la persona que tengo delante?", "standard"),
                                ("¿Qué expresión tiene su rostro?", "standard"),
                                ("Descríbeme a detalle su apariencia", "deep"),
                                ("¿Qué señales ves en su expresión?", "standard"),
                                ("What expression does she have?", "standard")):
            self.assertEqual(vision.classify(question)[:2], (level, "face"), question)
        # A photo with no question still carries the expression rule (a person may be the main subject).
        self.assertTrue(vision.plan("").people_focus)
        self.assertFalse(vision.plan("Lee esta página").people_focus)

    def test_facial_recognition_stays_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AINGEL_FACE_RECOGNITION_ENABLED", None)
            self.assertFalse(recognition_enabled())


@patch.dict(os.environ, PUBLIC)
class ExpressionPromptTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="expresiones"))
        self.profile = authorize(Profile.objects.create(owner=self.owner, display_name="Expresiones"),
                                 camera_local=True, meta_photos=True, meta_screen=True)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.provider = Provider(SAD)
        self.http = patch("assistance.vision.httpx.Client", self.provider)
        self.http.start()

    def tearDown(self):
        self.http.stop()
        bind_account(None)

    def describe(self, question="", **values):
        data = {"locale": "es-EC", "image": portrait(), "profile": str(self.profile.pk), **values}
        if question:
            data["question"] = question
        return self.client.post("/api/v1/vision/", data, format="multipart")

    def prompt(self, index=-1):
        return self.provider.prompt(index)

    def test_1_a_sad_portrait_puts_the_expression_before_the_anatomy(self):
        response = self.describe("¿Cómo se ve la persona que tengo delante?")
        self.assertEqual((response.status_code, response.data["task"]), (200, "face"))
        prompt = self.prompt()
        self.assertLess(prompt.index(EXPRESSIONS), prompt.index("FACES."))
        self.assertIn("start with their apparent expression and the visible cues behind it, then the facial features", prompt)
        # The answer is not rewritten: the expression Meta gave stays first.
        self.assertTrue(response.data["text"].startswith("El hombre parece triste"))

    def test_2_a_joyful_photo_asks_for_the_cues_right_after_the_expression(self):
        self.describe("¿Qué expresión tiene su rostro?")
        prompt = self.prompt()
        self.assertIn("«Su expresión transmite alegría»", prompt)
        self.assertLess(prompt.index("(1) Their apparent facial expression"), prompt.index("(2) Briefly, the visible cues"))
        self.assertIn("eyebrow position, eye opening, mouth curvature, lip tension, expression lines", prompt)
        self.assertIn("only cues that are really visible", prompt)

    def test_3_an_ambiguous_expression_is_not_stated_categorically(self):
        self.describe("¿Qué señales ves en su expresión?")
        self.assertIn("If the expression is ambiguous, say so and give the likely readings with their cues, never one "
                      "categorical emotion", self.prompt())

    def test_4_a_neutral_face_gets_no_invented_emotion(self):
        self.describe()
        self.assertIn("A neutral or relaxed face is described as neutral: never invent an emotion", self.prompt())

    def test_5_several_people_are_described_one_by_one(self):
        self.describe("Describe a las personas de la foto")
        self.assertIn("With several people, describe each one separately by position", self.prompt())
        self.assertIn("never mix their expressions or features", self.prompt())

    def test_6_a_specific_question_is_answered_first(self):
        for question in ("¿Cómo tiene el cabello?", "¿Qué ropa lleva?"):
            self.describe(question)
            prompt = self.prompt()
            self.assertIn(f"The person asks: «{question}»", prompt)
            self.assertIn("If the question asks about one specific detail, such as the hair or the clothes, answer that "
                          "first", prompt)

    def test_7_deep_keeps_the_expression_first_in_notes_and_synthesis(self):
        response = self.describe("Descríbeme a detalle su apariencia")
        self.assertEqual((response.status_code, response.data["steps"]), (200, 3), response.data)
        notes = sorted(self.provider.sent[:2], key=lambda payload: len(payload["input"][0]["content"]))
        self.assertIn(vision.EXPRESSION_NOTES, notes[0]["instructions"])
        self.assertIn(vision.EXPRESSION_CUES, notes[1]["instructions"])
        synthesis = self.prompt(2)
        self.assertIn(vision.EXPRESSION_SYNTHESIS.strip(), synthesis)
        for payload in self.provider.sent:
            self.assertIn(EXPRESSIONS, payload["instructions"])
            self.assertIn("The expression keeps first place at every level", payload["instructions"])
        # Depth is not reduced to save tokens.
        self.assertEqual((self.provider.sent[2]["reasoning"]["effort"], self.provider.sent[2]["max_output_tokens"]), ("high", 12000))
        # And a follow-up keeps the rules.
        self.client.post("/api/v1/vision/", {"locale": "es-EC", "session": response.data["session"],
                                              "question": "¿Y sus ojos?"}, format="multipart")
        self.assertIn(EXPRESSIONS, self.prompt())

    def test_8_screen_media_still_leaves_out_windows_when_a_person_is_shown(self):
        response = self.describe("¿Qué expresión tiene la persona del video?", source_kind="screen")
        self.assertEqual(response.status_code, 200, response.data)
        prompt = self.prompt()
        self.assertIn("SCREEN CONTENT.", prompt)
        self.assertIn("browser tabs and the address bar", prompt)
        self.assertIn(EXPRESSIONS, prompt)
        self.assertNotIn("name the application or window", prompt)

    def test_9_no_diagnoses_intentions_or_confirmed_mental_states_reach_meta_as_allowed(self):
        self.describe()
        prompt = self.prompt()
        self.assertIn("never state confirmed emotions, mental states, intentions, diagnoses or personality", prompt)
        self.assertIn("One photo or frame shows a single moment", prompt)
        self.assertIn("no headings such as «Emoción principal»", prompt)

    def test_10_consent_revocation_quota_and_privacy_still_apply(self):
        decide(self.profile, self.owner, "meta_photos", "decline")
        refused = self.describe()
        self.assertEqual(refused.data["error"], "privacy_review_required")
        self.assertEqual(self.provider.sent, [])
        decide(self.profile, self.owner, "meta_photos", "grant")
        response = self.describe()
        session = response.data["session"]
        self.assertNotIn(SAD.split(".")[0].encode(), cache.get(vision._key(session)))  # encrypted follow-up session
        with patch("assistance.vision.reserve_meta_call", side_effect=MetaQuotaError("meta_quota_exceeded")):
            self.assertEqual(self.describe().data["error"], "meta_quota_exceeded")
        decide(self.profile, self.owner, "meta_photos", "revoke")
        revoked = self.client.post("/api/v1/vision/", {"locale": "es-EC", "session": session, "question": "¿Y su boca?"}, format="multipart")
        self.assertIn(revoked.status_code, (403, 409))
        self.assertEqual(len(self.provider.sent), 1)


@patch.dict(os.environ, PUBLIC)
class SceneExpressionTests(TestCase):
    """Android «Ver y describir» (assistance.scene, POST scene/): brief, with the expression first."""

    def test_the_brief_scene_carries_the_expression_rules(self):
        owner = adult(get_user_model().objects.create_user(username="escena-expresion"))
        profile = authorize(Profile.objects.create(owner=owner, display_name="Escena"), camera_local=True, meta_photos=True)
        client = APIClient()
        client.force_authenticate(owner)
        with patch("assistance.scene.httpx.Client") as http:
            reply = http.return_value.__enter__.return_value.post.return_value
            reply.json.return_value = {"status": "completed", "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "Una mujer parece alegre: sonríe con los ojos entrecerrados."}]}]}
            response = client.post("/api/v1/scene/", {"locale": "es-EC", "image": portrait(), "profile": str(profile.pk)}, format="multipart")
            self.assertEqual(response.status_code, 200, response.data)
            instruction = http.return_value.__enter__.return_value.post.call_args.kwargs["json"]["input"][0]["content"][0]["text"]
        self.assertIn(EXPRESSIONS, instruction)
        self.assertIn("If a person is the main subject, the first sentence gives their apparent expression", instruction)
        self.assertIn("at most three short sentences", instruction)
        bind_account(None)
