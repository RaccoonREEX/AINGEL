"""Revocation is effective (second Astra audit): before a capture starts, while a request is pending, and before a
result is delivered. Layers kept apart: the operating system's permission lives on the device; these tests cover the
person's consent (care.consent) and the backend's authorization on every request.
"""

import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from assistance import synthetic

from .consent import decide
from .models import Profile
from .testing import adult, authorize

MOCK = {"AINGEL_AI_MODE": "mock", "AINGEL_VIDEO_CLIPS": "1"}
REAL = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0",
        "AINGEL_VIDEO_CLIPS": "1", "AINGEL_VIDEO_REAL": "1"}


class RevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.person = adult(get_user_model().objects.create_user(username="revocation-person"))
        self.profile = authorize(Profile.objects.create(owner=self.person, display_name="Ficticia"),
                                 camera_local=True, microphone_local=True, meta_photos=True, meta_video=True)
        self.client = APIClient()
        self.client.force_authenticate(self.person)

    def consent(self):
        return self.client.get(f"/api/v1/profiles/{self.profile.pk}/consent/").data

    def scene(self, path="scene"):
        data = {"image": SimpleUploadedFile("photo.jpg", synthetic.shapes_image(), "image/jpeg"), "locale": "es-EC",
                "profile": str(self.profile.pk)}
        if path == "locate":
            data["object_name"] = "taza"
        return self.client.post(f"/api/v1/{path}/", data, format="multipart")

    def clip(self, seq=1):
        return self.client.post("/api/v1/vision/clip/", {
            "clip": SimpleUploadedFile("clip.mp4", synthetic.moving_square_clip(), "video/mp4"), "locale": "es-EC",
            "profile": str(self.profile.pk), "session": "revocation-session", "seq": str(seq)}, format="multipart")

    def test_the_epoch_tells_clients_that_something_was_revoked(self):
        before = self.consent()["epoch"]
        self.assertIsNone(decide(self.profile, self.person, "meta_photos", "grant"))
        self.assertEqual(self.consent()["epoch"], before)  # granting does not interrupt anything
        self.assertIsNone(decide(self.profile, self.person, "camera_local", "revoke"))
        state = self.consent()
        self.assertGreater(state["epoch"], before)
        self.assertEqual({p["id"]: p["status"] for p in state["purposes"]}["camera_local"], "revoked")

    def test_after_revoking_the_camera_nothing_is_captured_even_by_a_test_server(self):
        with patch.dict(os.environ, MOCK):
            self.assertEqual(self.scene().status_code, 200)
            decide(self.profile, self.person, "camera_local", "revoke")
            with patch("assistance.views.describe_scene") as scene, patch("assistance.views.locate_object") as locate:
                for response in (self.scene(), self.scene("locate"), self.clip()):
                    self.assertEqual((response.status_code, response.data), (403, {"error": "camera_consent_revoked"}))
            scene.assert_not_called()
            locate.assert_not_called()
            # A new grant from the person is needed to use it again.
            decide(self.profile, self.person, "camera_local", "grant")
            self.assertEqual(self.scene().status_code, 200)

    def test_revoking_while_meta_looks_discards_the_late_answer(self):
        def revoked_meanwhile(*args, **kwargs):
            decide(self.profile, self.person, "meta_photos", "revoke")
            return {"text": "Una descripción que ya no debe entregarse.", "mode": "meta", "model": "m", "latency_ms": 1}

        with patch.dict(os.environ, REAL), patch("assistance.views.describe_scene", side_effect=revoked_meanwhile), \
                patch("assistance.views.family_matches", return_value=[]):
            response = self.scene()
        self.assertEqual((response.status_code, response.data), (409, {"error": "consent_changed"}))
        self.assertNotIn("debe entregarse", str(response.content))
        with patch.dict(os.environ, REAL), patch("assistance.views.describe_scene") as scene:
            self.assertEqual(self.scene().data, {"error": "privacy_review_required"})
        scene.assert_not_called()

    def test_revoking_during_a_clip_upload_discards_the_events_and_the_context(self):
        def revoked_meanwhile(*args, **kwargs):
            decide(self.profile, self.person, "meta_video", "revoke")
            return [{"kind": "entered", "what": "ZZQ-private", "certainty": "observed"}], "Entró alguien.", {}

        with patch.dict(os.environ, REAL), patch("assistance.video.describe_changes", side_effect=revoked_meanwhile):
            response = self.clip()
        self.assertEqual((response.status_code, response.data), (409, {"error": "consent_changed"}))
        decide(self.profile, self.person, "meta_video", "grant")
        with patch.dict(os.environ, REAL), patch("assistance.video.describe_changes", return_value=([], "", {})) as call:
            self.assertEqual(self.clip(seq=2).status_code, 200)
        self.assertEqual(call.call_args.args[2], [])  # nothing from before the revocation reaches the next clip
