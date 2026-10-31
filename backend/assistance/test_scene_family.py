import io
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from care.models import Membership, Profile
from care.testing import adult, authorize

from . import synthetic

MATEO = {"box": [0.2, 0.1, 0.6, 0.7], "candidate": {"id": "face-1", "display_name": "Mateo", "relationship": "Hijo"}}


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (320, 240), "gray").save(buffer, format="JPEG")
    return SimpleUploadedFile("frame.jpg", buffer.getvalue(), content_type="image/jpeg")


class SceneFamilyTests(TestCase):
    """«Qué ves» and continuous watching say which enrolled family member is in front (29-10-2026)."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="scene-owner"))
        self.son = adult(users.create_user(username="scene-son"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Owner", face_recognition_enabled=True)
        Membership.objects.create(profile=self.profile, user=self.son, relationship="Hijo")
        # The person's own grants: local family recognition, and their real photos to Meta (camera + photos).
        authorize(self.profile, face_local=True, camera_local=True, meta_photos=True)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post(self, family=True, locale="es-EC"):
        captured = {}

        def describe(image, loc, allowed, known_person=False, preferences=None):
            captured["known_person"] = known_person
            captured["allowed"] = allowed
            return {"text": "Lleva un suéter verde y mira el teléfono.", "mode": "meta", "model": "muse-spark-1.3", "latency_ms": 5}

        with patch.dict(os.environ, {"AINGEL_REAL_DATA": "1", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}), patch(
            "assistance.views.family_matches", return_value=[MATEO, {"box": [0, 0, 0.1, 0.1], "candidate": None}]
        ) as matches, patch("assistance.views.describe_scene", describe):
            response = self.client.post(
                "/api/v1/scene/",
                {"image": photo(), "locale": locale, "profile": str(self.profile.pk), "family": family},
                format="multipart",
            )
        return response, captured, matches

    def test_owner_hears_who_it_is_and_meta_only_describes_them(self):
        response, captured, _ = self.post()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["people"],
            [{"id": "face-1", "display_name": "Mateo", "relationship": "Hijo", "line": "Parece ser tu hijo Mateo."}],
        )
        self.assertTrue(captured["known_person"])
        self.assertEqual(captured["allowed"], synthetic.REAL)
        english, _, _ = self.post(locale="en-US")
        self.assertEqual(english.data["people"][0]["line"], "It looks like Mateo (Hijo).")

    def test_recognition_only_when_asked_by_the_owner_with_the_feature_on(self):
        response, captured, matches = self.post(family=False)
        self.assertEqual(response.data["people"], [])
        self.assertFalse(captured["known_person"])
        matches.assert_not_called()
        self.client.force_authenticate(self.son)
        response, _, matches = self.post()
        self.assertEqual(response.data["people"], [])
        matches.assert_not_called()
        self.client.force_authenticate(self.owner)
        self.profile.face_recognition_enabled = False
        self.profile.save()
        response, _, matches = self.post()
        self.assertEqual(response.data["people"], [])
        matches.assert_not_called()
