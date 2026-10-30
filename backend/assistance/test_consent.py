import io
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from care.models import Profile


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    return SimpleUploadedFile("frame.png", buffer.getvalue(), "image/png")


class SignUpConsentTests(TestCase):
    """Authorizations are given once, at sign-up, and the servers check them instead of asking per action."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = users.create_user(username="consent-owner")
        self.outsider = users.create_user(username="consent-outsider")
        self.profile = Profile.objects.create(owner=self.owner, display_name="Synthetic")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_consents_are_stamped_and_validated(self):
        url = f"/api/v1/profiles/{self.profile.id}/"
        response = self.client.patch(url, {"consents": {"camera": True, "microphone": True, "meta_data": True}}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        stored = Profile.objects.get(pk=self.profile.pk).consents
        self.assertEqual((stored["camera"], stored["meta_data"], stored["granted_by"]), (True, True, "consent-owner"))
        self.assertTrue(stored["version"] and stored["granted_at"])
        for bad in ({"camera": "yes"}, {"anything": True}, ["camera"]):
            self.assertEqual(self.client.patch(url, {"consents": bad}, format="json").status_code, 400)

    def describe(self, profile=None):
        data = {"image": png(), "locale": "es-EC"}
        if profile:
            data["profile"] = str(profile)
        return self.client.post("/api/v1/scene/", data, format="multipart")

    def test_real_image_needs_camera_and_meta_consent_of_an_accessible_profile(self):
        env = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1"}
        fake = {"text": "Una mesa.", "mode": "meta", "model": "muse-spark-1.3", "latency_ms": 1}
        with patch.dict(os.environ, env), patch("assistance.scene.call_meta_vision", return_value=fake, create=True):
            self.assertEqual(self.describe().data["error"], "privacy_review_required")
            self.assertEqual(self.describe(self.profile.id).data["error"], "privacy_review_required")
            self.profile.consents = {"camera": True, "microphone": False, "meta_data": True}
            self.profile.save()
            with patch("assistance.views.describe_scene", return_value=fake) as describe:
                self.assertEqual(self.describe(self.profile.id).status_code, 200)
                self.assertTrue(describe.call_args.args[2])
            self.client.force_authenticate(self.outsider)
            self.assertEqual(self.describe(self.profile.id).status_code, 404)
        with patch.dict(os.environ, {**env, "AINGEL_REAL_DATA": "0"}), patch("assistance.views.describe_scene", return_value=fake) as describe:
            self.client.force_authenticate(self.owner)
            self.describe(self.profile.id)
            self.assertFalse(describe.call_args.args[2])
