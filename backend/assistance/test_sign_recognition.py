"""Experimental sign recognition: authorized before any frame is read, exact payload, vocabulary only, revocation."""

import io
import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from care.consent import decide
from care.models import AuditEvent, Profile
from care.testing import adult, authorize

from .sign_recognition import VOCABULARY

REAL = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0",
        "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
PRIVATE = {**REAL, "AINGEL_PRIVATE_OWN_MEDIA_TEST": "1"}


def frame(color="white"):
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buffer, format="JPEG")
    return SimpleUploadedFile("frame.jpg", buffer.getvalue(), "image/jpeg")


class Wire:
    def __init__(self, signs):
        self.sent, self.signs = [], signs

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.sent.append(json)
        return self

    def raise_for_status(self):
        return None

    def json(self):
        arguments = __import__("json").dumps({"signs": self.signs, "observed": "Una mano abierta se mueve junto a la cabeza."})
        return {"status": "completed", "output": [{"type": "function_call", "name": "report_signs", "arguments": arguments}]}


class SignRecognitionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.person = adult(get_user_model().objects.create_user(username="signs-person"))
        self.profile = authorize(Profile.objects.create(owner=self.person, display_name="Ficticia"),
                                 camera_local=True, meta_photos=True)
        self.client = APIClient()
        self.client.force_authenticate(self.person)
        self.path = f"/api/v1/profiles/{self.profile.pk}/signs/recognize/"

    def post(self, count=4, **extra):
        return self.client.post(self.path, {"image": [frame() for _ in range(count)], "locale": "es-EC", **extra}, format="multipart")

    def test_recognized_signs_come_back_from_the_vocabulary_with_the_exact_payload(self):
        wire = Wire([{"id": "hola", "certainty": "likely"}, {"id": "gracias", "certainty": "uncertain"}])
        with patch.dict(os.environ, REAL), patch("assistance.sign_recognition.httpx.Client", wire):
            response = self.post(count=5)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["signs"], [{"id": "hola", "certainty": "likely"}, {"id": "gracias", "certainty": "uncertain"}])
        self.assertEqual((response.data["names"], response.data["experimental"]), (["hola", "gracias"], True))
        (payload,) = wire.sent
        images = [part for part in payload["input"][0]["content"] if part["type"] == "input_image"]
        self.assertEqual(len(images), 5)
        self.assertEqual(payload["tools"][0]["name"], "report_signs")
        self.assertEqual(payload["tools"][0]["parameters"]["properties"]["signs"]["items"]["properties"]["id"]["enum"], list(VOCABULARY))
        self.assertIn("Never identify the person", payload["instructions"])
        self.assertNotIn("Ficticia", json.dumps(payload))  # nothing of the profile goes with the frames
        self.assertTrue(AuditEvent.objects.filter(profile=self.profile, action="signs.recognize").exists())

    def test_an_invented_sign_rejects_the_whole_answer(self):
        wire = Wire([{"id": "hola", "certainty": "likely"}, {"id": "teletransporte", "certainty": "likely"}])
        with patch.dict(os.environ, REAL), patch("assistance.sign_recognition.httpx.Client", wire):
            response = self.post()
        self.assertEqual((response.status_code, response.data), (503, {"error": "sign_recognition_invalid"}))

    def test_nothing_is_read_or_sent_without_authorization(self):
        refusals = [
            ("no photos grant", lambda: decide(self.profile, self.person, "meta_photos", "revoke"), 400, "privacy_review_required"),
            ("camera refused", lambda: decide(self.profile, self.person, "camera_local", "revoke"), 403, "camera_consent_revoked"),
        ]
        for name, revoke, status, error in refusals:
            with self.subTest(name):
                revoke()
                with patch.dict(os.environ, REAL), patch("assistance.sign_recognition.httpx.Client") as provider, \
                        patch("assistance.sign_recognition.normalize_image") as read:
                    response = self.post()
                self.assertEqual((response.status_code, response.data), (status, {"error": error}))
                provider.assert_not_called()
                read.assert_not_called()

    def test_no_synthetic_path_and_bounded_frames(self):
        with patch.dict(os.environ, REAL), patch("assistance.sign_recognition.httpx.Client") as provider:
            self.assertEqual(self.post(synthetic="true").data, {"error": "sign_recognition_real_only"})
            self.assertEqual(self.post(count=2).data, {"error": "sign_frames_invalid"})
            self.assertEqual(self.post(count=7).data, {"error": "sign_frames_invalid"})
        provider.assert_not_called()

    def test_private_own_media_test_needs_the_owners_declaration(self):
        wire = Wire([{"id": "si", "certainty": "likely"}])
        with patch.dict(os.environ, PRIVATE), patch("assistance.sign_recognition.httpx.Client", wire):
            refused = self.post()
            accepted = self.post(private_test="true")
        self.assertEqual(refused.data, {"error": "privacy_review_required"})
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(len(wire.sent), 1)

    def test_revoking_while_meta_looks_discards_the_result(self):
        wire = Wire([{"id": "hola", "certainty": "likely"}])
        original = wire.post

        def revoked_meanwhile(*args, **kwargs):
            decide(self.profile, self.person, "meta_photos", "revoke")
            return original(*args, **kwargs)

        wire.post = revoked_meanwhile
        with patch.dict(os.environ, REAL), patch("assistance.sign_recognition.httpx.Client", wire):
            response = self.post()
        self.assertEqual((response.status_code, response.data), (409, {"error": "consent_changed"}))

    def test_mock_mode_sends_nothing(self):
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}), patch("assistance.sign_recognition.httpx.Client") as provider:
            response = self.post()
        self.assertEqual((response.status_code, response.data["mode"], response.data["signs"]), (200, "mock", []))
        provider.assert_not_called()
