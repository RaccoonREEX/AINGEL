import io
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from care.consent import private_media_allowed
from care.models import Membership, Profile
from care.testing import adult, authorize

from assistance import synthetic


PRIVATE = {
    "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key",
    "AINGEL_PRIVATE_OWN_MEDIA_TEST": "1", "AINGEL_REAL_DATA": "1",
    "AINGEL_SYNTHETIC_TESTS_ONLY": "0",
}
CONSENTS = {"camera": True, "microphone": True, "meta_data": True}


def image():
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buf, "PNG")
    return SimpleUploadedFile("test.png", buf.getvalue(), "image/png")


class PrivateMediaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = adult(get_user_model().objects.create_user(username="private-owner"))
        self.caregiver = adult(get_user_model().objects.create_user(username="private-caregiver"))
        self.profile = Profile.objects.create(
            owner=self.owner, display_name="Owner", consents=CONSENTS,
            support_notes="PRIVATE_CONDITION", allergies="PRIVATE_ALLERGY",
            face_recognition_enabled=True,
        )
        authorize(self.profile, CONSENTS)
        Membership.objects.create(profile=self.profile, user=self.caregiver, relationship="family")
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post_image(self, path="scene", **values):
        return self.client.post(f"/api/v1/{path}/", {
            "image": image(), "locale": "es-EC", "profile": str(self.profile.pk), **values,
        }, format="multipart")

    def test_all_server_switches_owner_declaration_and_consents_required(self):
        with patch.dict(os.environ, PRIVATE):
            self.assertTrue(private_media_allowed(self.profile, self.owner, "image", True))
            self.assertTrue(private_media_allowed(self.profile, self.owner, "audio", True))
            self.assertFalse(private_media_allowed(self.profile, self.caregiver, "image", True))
            self.assertFalse(private_media_allowed(self.profile, self.owner, "image", 1))
            self.assertFalse(private_media_allowed(self.profile, self.owner, "conversation", True))
            for key in ("camera", "meta_data"):
                authorize(self.profile, {**CONSENTS, key: False})
                self.assertFalse(private_media_allowed(self.profile, self.owner, "image", True))
            authorize(self.profile, {**CONSENTS, "microphone": False})
            self.assertFalse(private_media_allowed(self.profile, self.owner, "audio", True))
            for key, wrong in (("AINGEL_REAL_DATA", "0"), ("AINGEL_PRIVATE_OWN_MEDIA_TEST", "0"), ("AINGEL_SYNTHETIC_TESTS_ONLY", "1")):
                with patch.dict(os.environ, {key: wrong}):
                    self.assertFalse(private_media_allowed(self.profile, self.owner, "audio", True))
            # The private own-media test is not a synthetic-test server: no fixture runs, and a declaration never counts.
            self.assertFalse(synthetic.enabled())
            self.assertEqual(synthetic.route({"fixture": "greeting"}, "question", False, ()), (None, "synthetic_tests_disabled"))
            self.assertEqual(synthetic.route({"synthetic": True}, "question", True, ()), (None, "synthetic_fixture_required"))
        with patch.dict(os.environ, {"AINGEL_SYNTHETIC_TESTS_ONLY": "1"}):
            self.assertTrue(synthetic.enabled())
            self.assertEqual(synthetic.route({"fixture": "greeting"}, "question", False, ()), ("fixture", "greeting"))
            for flag in (True, False):
                self.assertEqual(synthetic.route({"synthetic": flag}, "question", True, ()), (None, "synthetic_fixture_required"))
                self.assertEqual(synthetic.route({"synthetic": flag, "fixture": "greeting"}, "question", False, ()), (None, "synthetic_fixture_required"))

    def test_scene_and_locate_gate_before_provider_and_disable_family_matching(self):
        with patch.dict(os.environ, PRIVATE), patch("assistance.scene.httpx.Client") as provider:
            response = self.post_image(private_test=False)
            self.assertEqual(response.data["error"], "privacy_review_required")
            provider.assert_not_called()
            self.client.force_authenticate(self.caregiver)
            response = self.post_image(private_test=True)
            self.assertEqual(response.data["error"], "privacy_review_required")
            provider.assert_not_called()
        self.client.force_authenticate(self.owner)
        result = {"text": "test", "mode": "meta", "model": "test", "latency_ms": 1}
        with patch.dict(os.environ, PRIVATE), patch("assistance.views.describe_scene", return_value=result) as scene, patch("assistance.views.family_matches") as match:
            response = self.post_image(private_test=True, family=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(scene.call_args.args[2], synthetic.REAL)
            self.assertFalse(scene.call_args.kwargs["known_person"])
            match.assert_not_called()
        with patch.dict(os.environ, PRIVATE), patch("assistance.views.locate_object", return_value={"matches": []}) as locate:
            response = self.post_image("locate", private_test=True, object_name="cup")
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(locate.call_args.args[2], synthetic.REAL)

    def test_personal_text_endpoints_blocked_even_with_consent(self):
        with patch.dict(os.environ, PRIVATE), patch("assistance.conversation.call_spark") as converse, patch("assistance.companion.call_spark") as companion, patch("assistance.gloss.call_spark") as gloss:
            base = f"/api/v1/profiles/{self.profile.pk}"
            for path, data in (
                ("conversation/", {"turns": [{"role": "user", "text": "hello"}]}),
                ("companion/chat/", {"text": "hello"}),
                ("signs/gloss/", {"text": "hello", "vocabulary": {"hello": "hello"}}),
            ):
                response = self.client.post(f"{base}/{path}", data, format="json")
                self.assertEqual(response.data.get("error"), "privacy_review_required", path)
            converse.assert_not_called()
            companion.assert_not_called()
            gloss.assert_not_called()
