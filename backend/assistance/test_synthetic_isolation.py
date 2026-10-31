"""Synthetic isolation (Astra audit, 30-10-2026): every request that would reach Meta is intercepted at the HTTP
client and its exact payload inspected.

A profile full of fictitious private markers (name, preferences, support needs, allergies, notes, contact, memory,
routine, message) belongs to the caller. Synthetic tests must send only server fixtures with a fictitious profile;
a client calling its own content synthetic must be refused before any payload is built.
"""

import base64
import json
import os
from datetime import time as clock
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from care.models import Memory, Message, Profile, Routine
from care.testing import adult, authorize
from config.asgi import application

from . import synthetic
from .companion import CompanionUnavailable, call_spark
from .locate import locate_object
from .scene import SceneUnavailable, describe_scene
from .video import VideoUnavailable, describe_changes

MARKERS = (
    "ZZQ-NAME", "ZZQ-PREFERRED", "ZZQ-ALLERGY", "ZZQ-DIAGNOSIS", "ZZQ-NOTE", "ZZQ-CONTACT",
    "ZZQ-MEMORY", "ZZQ-ROUTINE", "ZZQ-MESSAGE", "ZZQ-CLIENT",
)
# The private profile's style differs from the fictitious defaults in every field.
PRIVATE_STYLE = {
    "addressing": "formal", "preferred_name": "ZZQ-PREFERRED", "sentence_length": "standard", "pace": "slow",
    "interaction": "standard", "detail": "detailed", "repeat_important": "yes", "spontaneous": "many",
    "distress": "contact_caregiver", "priority_support": "cognitive",
}
META = {
    "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
    "AINGEL_REAL_DATA": "0", "AINGEL_VIDEO_CLIPS": "1",
}
ANSWER = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "Respuesta de prueba."}]}]}


class Wire:
    """Stands in for httpx.Client in every Meta module and records each request exactly as it would be sent."""

    def __init__(self):
        self.sent = []

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None, data=None, files=None):
        self.sent.append({"url": url, "json": json, "data": data, "files": files})
        return Reply()

    def stream(self, method, url, headers=None, json=None):
        self.sent.append({"url": url, "json": json})
        return Reply()

    def delete(self, url, headers=None):
        return Reply()

    def text(self):
        return json.dumps(self.sent, ensure_ascii=False, default=repr)


class Reply:
    status_code = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    def json(self):
        return ANSWER

    def iter_bytes(self):
        yield json.dumps(ANSWER).encode()


def wire():
    recorder = Wire()
    patches = [patch(f"assistance.{module}.httpx.Client", recorder) for module in ("companion", "scene", "locate", "video")]
    return recorder, patches


class PrivateProfileMixin:
    def make_private_profile(self):
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="isolation-owner"))
        self.profile = Profile.objects.create(
            owner=self.owner, display_name="ZZQ-NAME", locale="en-US", allergies="ZZQ-ALLERGY",
            support_notes="Apoyos indicados: ZZQ-DIAGNOSIS\nZZQ-NOTE", emergency_contact="ZZQ-CONTACT",
            communication=PRIVATE_STYLE, face_recognition_enabled=True,
        )
        Memory.objects.create(profile=self.profile, entity="ZZQ-MEMORY", location="ZZQ-MEMORY", recorded_by=self.owner,
                              observed_at=timezone.now(), expires_at=timezone.now() + timedelta(days=1))
        Routine.objects.create(profile=self.profile, category="other", title="ZZQ-ROUTINE", at=clock(9), created_by=self.owner)
        Message.objects.create(profile=self.profile, author=self.owner, body="ZZQ-MESSAGE", locale="es-EC")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def assert_clean(self, recorder):
        text = recorder.text()
        for marker in MARKERS:
            self.assertNotIn(marker, text)
        for key, value in PRIVATE_STYLE.items():
            self.assertNotIn(f'"{key}": "{value}"', text.replace('\\"', '"'))


class SyntheticIsolationTests(PrivateProfileMixin, TestCase):
    def setUp(self):
        cache.clear()
        self.make_private_profile()
        self.base = f"/api/v1/profiles/{self.profile.pk}/"
        self.recorder, self.patches = wire()
        for item in self.patches:
            item.start()
        self.env = patch.dict(os.environ, META)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for item in self.patches:
            item.stop()

    def post(self, path, data, multipart=False):
        return self.client.post(path, data, format="multipart" if multipart else "json")

    def client_photo(self):
        return SimpleUploadedFile("photo.png", synthetic.shapes_image(), "image/jpeg")

    def client_clip(self):
        return SimpleUploadedFile("clip.mp4", synthetic.moving_square_clip(), "video/mp4")

    # --- A client's declaration is never evidence --------------------------------------------------------------

    def test_declared_synthetic_free_content_is_refused_everywhere_before_any_payload(self):
        attempts = [
            (self.base + "conversation/", {"turns": [{"role": "user", "text": "ZZQ-CLIENT"}], "synthetic": True}, False),
            (self.base + "companion/chat/", {"text": "ZZQ-CLIENT", "synthetic": True}, False),
            ("/api/v1/scene/", {"image": self.client_photo(), "locale": "es-EC", "synthetic": "true"}, True),
            ("/api/v1/locate/", {"image": self.client_photo(), "locale": "es-EC", "object_name": "ZZQ-CLIENT",
                                 "synthetic": "true"}, True),
            ("/api/v1/vision/clip/", {"clip": self.client_clip(), "locale": "es-EC", "session": "isolation-1",
                                      "seq": "1", "synthetic": "true"}, True),
            (self.base + "signs/gloss/", {"text": "ZZQ-CLIENT", "vocabulary": {"hola": "hola"}, "synthetic": True}, False),
        ]
        for path, data, multipart in attempts:
            with self.subTest(path=path):
                response = self.post(path, data, multipart)
                self.assertEqual(response.status_code, 400)
                self.assertIn(response.data["error"], ("synthetic_fixture_required", "gloss_request_invalid"))
        self.assertEqual(self.recorder.sent, [])

    def test_declared_synthetic_with_a_fixture_is_still_refused(self):
        response = self.post(self.base + "conversation/", {"fixture": "greeting", "synthetic": True})
        self.assertEqual(response.data["error"], "synthetic_fixture_required")
        self.assertEqual(self.recorder.sent, [])

    def test_free_content_next_to_a_fixture_is_refused(self):
        attempts = [
            (self.base + "conversation/", {"fixture": "greeting", "turns": [{"role": "user", "text": "ZZQ-CLIENT"}]}, False),
            (self.base + "conversation/", {"fixture": "greeting", "actions": ["describe_surroundings"]}, False),
            (self.base + "companion/chat/", {"fixture": "greeting", "text": "ZZQ-CLIENT"}, False),
            ("/api/v1/scene/", {"fixture": "shapes", "image": self.client_photo(), "locale": "es-EC"}, True),
            ("/api/v1/scene/", {"fixture": "shapes", "profile": str(self.profile.pk), "family": "true", "locale": "es-EC"}, True),
            ("/api/v1/locate/", {"fixture": "red_circle", "object_name": "ZZQ-CLIENT", "locale": "es-EC"}, True),
            ("/api/v1/vision/clip/", {"fixture": "moving_square", "clip": self.client_clip(), "locale": "es-EC",
                                      "session": "isolation-2", "seq": "1"}, True),
            ("/api/v1/vision/clip/", {"fixture": "moving_square", "profile": str(self.profile.pk), "locale": "es-EC",
                                      "session": "isolation-3", "seq": "1"}, True),
        ]
        for path, data, multipart in attempts:
            with self.subTest(path=path, fields=sorted(k for k in data if k != "fixture")):
                response = self.post(path, data, multipart)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"], "synthetic_fixture_only")
        self.assertEqual(self.recorder.sent, [])

    def test_unknown_fixtures_and_disabled_test_mode_send_nothing(self):
        response = self.post(self.base + "conversation/", {"fixture": "ZZQ-CLIENT"})
        self.assertEqual(response.data["error"], "synthetic_fixture_invalid")
        with patch.dict(os.environ, {"AINGEL_SYNTHETIC_TESTS_ONLY": "0"}):
            response = self.post(self.base + "conversation/", {"fixture": "greeting"})
        self.assertEqual(response.data["error"], "synthetic_tests_disabled")
        self.assertEqual(self.recorder.sent, [])

    def test_without_authorization_free_content_never_reaches_meta(self):
        attempts = [
            (self.base + "conversation/", {"turns": [{"role": "user", "text": "ZZQ-CLIENT"}]}, False),
            (self.base + "companion/chat/", {"text": "ZZQ-CLIENT"}, False),
            ("/api/v1/scene/", {"image": self.client_photo(), "locale": "es-EC", "profile": str(self.profile.pk)}, True),
            ("/api/v1/locate/", {"image": self.client_photo(), "locale": "es-EC", "object_name": "ZZQ-CLIENT"}, True),
            ("/api/v1/vision/clip/", {"clip": self.client_clip(), "locale": "es-EC", "session": "isolation-4", "seq": "1"}, True),
            (self.base + "signs/gloss/", {"text": "ZZQ-CLIENT", "vocabulary": {"hola": "hola"}}, False),
        ]
        for path, data, multipart in attempts:
            with self.subTest(path=path):
                response = self.post(path, data, multipart)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"], "privacy_review_required")
        self.assertEqual(self.recorder.sent, [])

    # --- Fixtures: the server's content, a fictitious profile ---------------------------------------------------

    def instructions(self, sent):
        payload = sent["json"]
        if "instructions" in payload:
            return payload["instructions"]
        return payload["input"][0]["content"][0]["text"]

    def assert_fictitious(self, sent, language="Spanish"):
        text = self.instructions(sent)
        self.assertIn(json.dumps(synthetic.FICTIONAL_PREFERENCES, ensure_ascii=True), text)
        self.assertIn(f"Respond in {language}", text)  # the fixture's language, not the profile's (en-US)

    def test_conversation_fixture_sends_only_the_server_question(self):
        response = self.post(self.base + "conversation/", {"fixture": "hydration"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["synthetic_fixture"], "hydration")
        (sent,) = self.recorder.sent
        self.assert_clean(self.recorder)
        self.assert_fictitious(sent)
        body = json.loads(sent["json"]["input"][0]["content"][0]["text"])
        self.assertEqual(body["current_synthetic_question"], synthetic.QUESTIONS["hydration"]["es-EC"])
        self.assertEqual(body["conversation_history"], [])
        self.assertNotIn("support_needs", body)
        self.assertNotIn("allergies", body)
        self.assertNotIn("tools", sent["json"])  # no web search, no app actions

    def test_companion_fixture_sends_only_the_server_question(self):
        response = self.post(self.base + "companion/chat/", {"fixture": "greeting", "locale": "en-US"})
        self.assertEqual(response.status_code, 200, response.data)
        (sent,) = self.recorder.sent
        self.assert_clean(self.recorder)
        self.assert_fictitious(sent, "English")
        body = json.loads(sent["json"]["input"][0]["content"][0]["text"])
        self.assertEqual(body, {"synthetic_question": synthetic.QUESTIONS["greeting"]["en-US"]})

    def test_scene_fixture_sends_the_server_image_without_recognition(self):
        with patch("assistance.views.family_matches") as faces:
            response = self.post("/api/v1/scene/", {"fixture": "shapes", "locale": "es-EC"}, True)
        self.assertEqual(response.status_code, 200, response.data)
        faces.assert_not_called()
        self.assertEqual(response.data["people"], [])
        (sent,) = self.recorder.sent
        self.assert_clean(self.recorder)
        self.assert_fictitious(sent)
        image = sent["json"]["input"][0]["content"][1]["image_url"]
        self.assertEqual(image, "data:image/jpeg;base64," + base64.b64encode(synthetic.shapes_image()).decode("ascii"))

    def test_locate_fixture_sends_the_server_image_and_object(self):
        self.post("/api/v1/locate/", {"fixture": "red_circle", "locale": "es-EC"}, True)
        (sent,) = self.recorder.sent
        self.assert_clean(self.recorder)
        content = sent["json"]["input"][0]["content"]
        self.assertEqual(content[0]["text"], "red circle")
        self.assertEqual(content[1]["image_url"], "data:image/jpeg;base64," + base64.b64encode(synthetic.shapes_image()).decode("ascii"))

    def test_video_fixture_sends_the_server_clip(self):
        response = self.post("/api/v1/vision/clip/", {"fixture": "moving_square", "locale": "es-EC",
                                                      "session": "isolation-5", "seq": "1"}, True)
        self.assertEqual(response.status_code, 200, response.data)
        (sent,) = self.recorder.sent
        self.assert_clean(self.recorder)
        self.assert_fictitious(sent)
        video = sent["json"]["input"][0]["content"][1]
        self.assertEqual(video["video_url"], "data:video/mp4;base64," + base64.b64encode(synthetic.moving_square_clip()).decode("ascii"))

    def test_catalog_lists_fixture_ids_and_texts(self):
        response = self.client.get("/api/v1/synthetic/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["enabled"])
        self.assertFalse(response.data["captions"])
        self.assertEqual({q["id"] for q in response.data["questions"]}, set(synthetic.QUESTIONS))

    # --- The separate real path still works, only with the person's own grants ----------------------------------

    def test_real_path_needs_the_persons_grants_and_sends_only_what_they_cover(self):
        authorize(self.profile, meta_conversation=True)
        with patch.dict(os.environ, {"AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}):
            response = self.post(self.base + "conversation/", {"turns": [{"role": "user", "text": "¿Qué hora es en Quito?"}]})
        self.assertEqual(response.status_code, 200, response.data)
        (sent,) = self.recorder.sent
        body = json.loads(sent["json"]["input"][0]["content"][0]["text"])
        self.assertEqual(body["current_question"], "¿Qué hora es en Quito?")
        # The person's style preferences go with their own question (assistance.persona), but without
        # «profile_personalization» no name, note, support need, allergy nor the sensitive preference.
        text = self.recorder.text()
        for marker in MARKERS:
            self.assertNotIn(marker, text)
        self.assertNotIn("priority_support", self.instructions(sent))

    # --- Defence in depth: provider functions refuse without a decided basis --------------------------------------

    def test_provider_functions_refuse_without_a_basis(self):
        for call, error in [
            (lambda: call_spark("rules", "ZZQ-CLIENT"), CompanionUnavailable),
            (lambda: call_spark("rules", "ZZQ-CLIENT", basis=True), CompanionUnavailable),
            (lambda: describe_scene(synthetic.shapes_image(), "es-EC", True), SceneUnavailable),
            (lambda: locate_object(synthetic.shapes_image(), "ZZQ-CLIENT", True), SceneUnavailable),
            (lambda: describe_changes(synthetic.moving_square_clip(), "es-EC", [], {}), VideoUnavailable),
        ]:
            with self.assertRaises(error) as raised:
                call()
            self.assertEqual(str(raised.exception), "privacy_review_required")
        self.assertEqual(self.recorder.sent, [])


class SyntheticCaptionTests(PrivateProfileMixin, TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.make_private_profile()
        self.client.force_login(self.owner)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    async def start(self, message):
        ws = WebsocketCommunicator(application, "/ws/captions/",
                                   headers=[(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)])
        connected, _ = await ws.connect()
        self.assertTrue(connected)
        await ws.send_to(text_data=json.dumps(message))
        reply = json.loads(await ws.receive_from())
        await ws.disconnect()
        return reply

    def test_declared_synthetic_audio_never_opens_the_provider(self):
        with patch.dict(os.environ, META), patch("assistance.captions.connect", new=AsyncMock()) as connect:
            for message in (
                {"type": "start", "locale": "es-EC", "synthetic": True},
                {"type": "start", "locale": "es-EC", "fixture": "greeting"},
                {"type": "start", "locale": "es-EC", "synthetic": True, "profile": str(self.profile.pk)},
                {"type": "start", "locale": "es-EC", "profile": str(self.profile.pk)},  # no voice grant
            ):
                with self.subTest(message=message):
                    reply = async_to_sync(self.start)(message)
                    self.assertEqual(reply["type"], "error")
                    self.assertIn(reply["code"], ("synthetic_captions_unavailable", "privacy_review_required"))
            connect.assert_not_called()
