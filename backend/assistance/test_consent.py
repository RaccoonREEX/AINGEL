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
from care.consent import CONSENT_VERSION
from care.models import ConsentGrant
from care.testing import adult, authorize


def png():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, "PNG")
    return SimpleUploadedFile("frame.png", buffer.getvalue(), "image/png")


class SignUpConsentTests(TestCase):
    """Authorizations are given once, at sign-up, and the servers check them instead of asking per action."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="consent-owner"))
        self.outsider = adult(users.create_user(username="consent-outsider"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Synthetic")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_decisions_are_recorded_with_purpose_version_who_and_when(self):
        authorize(self.profile)
        url = f"/api/v1/profiles/{self.profile.id}/consent/"
        response = self.client.post(url, {"purpose": "camera_local", "decision": "grant"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        grant = ConsentGrant.objects.get(profile=self.profile, purpose="camera_local")
        self.assertEqual((grant.status, grant.decided_by, grant.method, grant.version), ("granted", self.owner, "own_account", CONSENT_VERSION))
        for bad in ({"purpose": "everything", "decision": "grant"}, {"purpose": "camera_local", "decision": "maybe"}, {"purpose": "camera_local"}):
            self.assertEqual(self.client.post(url, bad, format="json").status_code, 400, bad)

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
            authorize(self.profile, {"camera": True, "microphone": False, "meta_data": True})
            with patch("assistance.views.describe_scene", return_value=fake) as describe:
                self.assertEqual(self.describe(self.profile.id).status_code, 200)
                self.assertTrue(describe.call_args.args[2])
            self.client.force_authenticate(self.outsider)
            self.assertEqual(self.describe(self.profile.id).status_code, 404)
        with patch.dict(os.environ, {**env, "AINGEL_REAL_DATA": "0"}), patch("assistance.views.describe_scene", return_value=fake) as describe:
            self.client.force_authenticate(self.owner)
            self.describe(self.profile.id)
            self.assertFalse(describe.call_args.args[2])
