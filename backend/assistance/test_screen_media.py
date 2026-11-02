"""AINGEL Desktop's screen captures (source_kind «screen») are described by the media or documents on them, not by the
computer's interface (assistance.vision «screen_media»); the interface is described only when the person asks about
it («screen»). Requests to Meta are intercepted at the HTTP client: these tests check what AINGEL instructs Meta, at
every step, and that permissions, encrypted sessions, quotas and revocation still apply."""

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

from . import vision
from .meta_quota import MetaQuotaError, bind_account
from .test_vision import Provider

# Production with consent: the person's own screen, under their «meta_screen» grant.
PUBLIC = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1",
          "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
MEDIA_RULES = "SCREEN CONTENT."
INTERFACE_RULES = "COMPUTER SCREEN."
INTERFACE_FOCUS = "name the application or window"
NO_MEDIA = vision.NO_MEDIA["es-EC"]


def screenshot():
    """A synthetic screen: a browser-like frame with a picture in it (bars, tabs and a photo-like block)."""
    image = Image.new("RGB", (640, 400), (240, 240, 240))
    for y, colour in ((0, (60, 60, 60)), (30, (210, 210, 210)), (370, (30, 30, 30))):
        image.paste(colour, (0, y, 640, y + 30))
    image.paste((40, 110, 180), (120, 90, 520, 340))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return SimpleUploadedFile("pantalla.png", buffer.getvalue(), "image/png")


class ScreenClassificationTests(TestCase):
    def test_a_screen_capture_is_about_its_media_unless_the_interface_is_asked(self):
        for question in ("", "Describe mi pantalla", "¿Qué se ve en el video?", "Describe la imagen del navegador"):
            self.assertEqual(vision.classify(question, "screen")[1], "screen_media", question)
        for question in ("¿Qué botones hay?", "Lee la barra de herramientas", "¿Qué ventanas tengo abiertas?",
                         "¿Qué programa es?", "What is on the taskbar?"):
            self.assertEqual(vision.classify(question, "screen")[1], "screen", question)
        # A window, a desk or a restaurant menu inside the content is content, not the interface.
        for question in ("¿Qué se ve por la ventana?", "¿Qué hay sobre el escritorio de la foto?", "Lee el menú del restaurante"):
            self.assertNotEqual(vision.classify(question, "screen")[1], "screen", question)
        # Eyelashes are not browser tabs; and a document or a face on the screen keeps its own task.
        self.assertEqual(vision.classify("¿Cómo son sus pestañas?", "screen")[1], "face")
        self.assertEqual(vision.classify("Lee el PDF", "screen")[1], "document")
        # Photos from the camera are unchanged.
        self.assertEqual(vision.classify("¿Qué hay en la pantalla?", "camera")[1], "screen")

    def test_media_focus_applies_to_every_task_on_a_screen_except_the_interface(self):
        self.assertTrue(vision.plan("", source_kind="screen").media_focus)
        self.assertTrue(vision.plan("Lee el PDF", source_kind="screen").media_focus)
        self.assertFalse(vision.plan("¿Qué botones hay?", source_kind="screen").media_focus)
        self.assertFalse(vision.plan("", source_kind="camera").media_focus)
        # A follow-up keeps the media focus, and switches to the interface only when asked.
        self.assertEqual(vision.plan("¿Y qué más?", source_kind="screen", previous="screen_media").task, "screen_media")
        self.assertEqual(vision.plan("¿Qué botones hay?", source_kind="screen", previous="screen_media").task, "screen")


@patch.dict(os.environ, PUBLIC)
class ScreenMediaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="pantalla-media"))
        self.profile = authorize(Profile.objects.create(owner=self.owner, display_name="Pantalla"), meta_screen=True)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.provider = Provider("Se observa a un hombre caminando por una calle concurrida.")
        self.http = patch("assistance.vision.httpx.Client", self.provider)
        self.http.start()

    def tearDown(self):
        self.http.stop()
        bind_account(None)

    def describe(self, **values):
        data = {"locale": "es-EC", "image": screenshot(), "profile": str(self.profile.pk), "source_kind": "screen", **values}
        return self.client.post("/api/v1/vision/", data, format="multipart")

    def follow(self, session, **values):
        return self.client.post("/api/v1/vision/", {"locale": "es-EC", "session": session, **values}, format="multipart")

    def assert_media_prompt(self, prompt):
        self.assertIn(MEDIA_RULES, prompt)
        self.assertIn("browser tabs and the address bar", prompt)
        self.assertIn("Never open with or mention a capture, screenshot, screen, monitor, operating system", prompt)
        self.assertIn(NO_MEDIA, prompt)
        self.assertNotIn(INTERFACE_RULES, prompt)
        self.assertNotIn(INTERFACE_FOCUS, prompt)

    def test_an_image_in_a_browser_is_described_without_the_browser(self):
        response = self.describe()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["task"], "screen_media")
        prompt = self.provider.prompt()
        self.assert_media_prompt(prompt)
        self.assertIn("a photograph or an animation; an image, drawing or illustration", prompt)
        self.assertEqual(response.data["text"], "Se observa a un hombre caminando por una calle concurrida.")

    def test_a_video_is_described_by_its_visible_scene_in_one_still_frame(self):
        response = self.describe(question="¿Qué se ve en el video?")
        self.assertEqual(response.status_code, 200, response.data)
        prompt = self.provider.prompt()
        self.assert_media_prompt(prompt)
        self.assertIn("for a video, the visible scene", prompt)
        self.assertIn("never attribute continuous movement, sound, dialogue or events before or after it", prompt)
        self.assertIn("never guess what it shows", prompt)  # a black, protected video area is not filled in

    def test_a_pdf_is_described_by_its_content_not_its_program(self):
        response = self.describe(question="Lee el PDF que tengo abierto")
        self.assertEqual((response.status_code, response.data["task"]), (200, "document"))
        prompt = self.provider.prompt()
        self.assert_media_prompt(prompt)
        self.assertIn("Identify a document by its content, never by the program showing it", prompt)
        self.assertIn("read the visible text in order without inventing words", prompt)

    def test_a_screen_without_media_gets_only_the_no_media_sentence(self):
        # Even if the model adds an invented description around it, only the sentence is shown and spoken.
        self.provider.text = NO_MEDIA + " Hay una barra de tareas con iconos y una ventana abierta."
        response = self.describe()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual((response.data["text"], response.data["paragraphs"]), (NO_MEDIA, [NO_MEDIA]))
        self.assertNotIn("barra de tareas", str(response.data))

    def test_a_follow_up_keeps_the_media_focus(self):
        session = self.describe().data["session"]
        response = self.follow(session, question="¿Y qué lleva puesto?")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(self.provider.sent), 2)
        self.assert_media_prompt(self.provider.prompt())
        self.assertIn("Earlier about this same image the person asked", self.provider.prompt())

    def test_the_interface_is_described_only_when_asked_in_its_separate_mode(self):
        session = self.describe().data["session"]
        response = self.follow(session, question="¿Qué botones hay en la ventana?")
        self.assertEqual((response.status_code, response.data["task"]), (200, "screen"))
        prompt = self.provider.prompt()
        self.assertIn(INTERFACE_RULES, prompt)
        self.assertIn(INTERFACE_FOCUS, prompt)
        self.assertNotIn(MEDIA_RULES, prompt)
        # Explicitly from Desktop or the API, too.
        response = self.describe(visual_task="screen")
        self.assertEqual(response.data["task"], "screen")
        self.assertIn(INTERFACE_FOCUS, self.provider.prompt())

    def test_deep_never_narrates_windows_or_toolbars_at_any_step(self):
        response = self.describe(detail_level="deep")
        self.assertEqual((response.status_code, response.data["steps"]), (200, 3), response.data)
        notes = sorted(self.provider.sent[:2], key=lambda payload: len(payload["input"][0]["content"]))
        for payload in notes:
            self.assert_media_prompt(payload["instructions"])
            self.assertIn(vision.MEDIA_NOTES, payload["instructions"])
        synthesis = self.provider.prompt(2)
        self.assert_media_prompt(synthesis)
        self.assertIn("If the notes found no media or document, give only the sentence", synthesis)
        # Depth is kept: the deep budgets and effort are unchanged.
        self.assertEqual((self.provider.sent[2]["reasoning"]["effort"], self.provider.sent[2]["max_output_tokens"]), ("high", 12000))
        # And a deep follow-up keeps it too.
        self.follow(response.data["session"], detail_level="deep")
        for payload in self.provider.sent[3:]:
            self.assert_media_prompt(payload["instructions"])

    def test_permissions_sessions_quotas_and_revocation_still_apply(self):
        # Without the screen grant nothing is sent.
        decide(self.profile, self.owner, "meta_screen", "revoke")
        refused = self.describe()
        self.assertEqual((refused.status_code, refused.data["error"]), (403, "screen_consent_revoked"))
        self.assertEqual(self.provider.sent, [])
        decide(self.profile, self.owner, "meta_screen", "grant")
        # The follow-up session is encrypted in the cache: neither the token nor the answer is readable there.
        response = self.describe()
        session = response.data["session"]
        sealed = cache.get(vision._key(session))
        self.assertNotIn(session.encode(), sealed)
        self.assertNotIn("calle concurrida".encode(), sealed)
        # The quota still stops a request before Meta.
        with patch("assistance.vision.reserve_meta_call", side_effect=MetaQuotaError("meta_quota_exceeded")):
            limited = self.describe()
        self.assertEqual(limited.data["error"], "meta_quota_exceeded")
        self.assertEqual(len(self.provider.sent), 1)
        # Revoking ends the session: the follow-up is refused and the picture is deleted.
        decide(self.profile, self.owner, "meta_screen", "revoke")
        revoked = self.follow(session, question="¿Y el fondo?")
        self.assertIn(revoked.status_code, (403, 409))
        self.assertEqual(self.follow(session, question="¿Y el fondo?").data["error"], "visual_session_expired")
        self.assertEqual(len(self.provider.sent), 1)
