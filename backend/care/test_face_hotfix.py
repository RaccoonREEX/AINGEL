"""Facial-privacy hotfix (31-10-2026).

1. Off by default (AINGEL_FACE_RECOGNITION_ENABLED): no route detects faces, computes or compares templates or
   enrolls anyone. OpenCV's face models are replaced by spies that fail the test if anything reaches them, and the
   image readers by spies that show nothing was even read. Looking and withdrawing keep working; templates stay
   until someone asks to delete them.
2. Once switched on again: the authorization is checked before processing and again after it; a revocation while
   OpenCV runs (also from another thread, truly concurrent) discards the result.
"""

import io
import os
import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from .consent import decide
from .crypto import encrypt
from .faces import FaceConsentChanged, FaceRecognitionDisabled, embeddings, family_matches
from .models import AuditEvent, FamilyFace, Membership, Profile
from .testing import adult, authorize

VECTOR = [1.0] + [0.0] * 127
# The real, authorized path of scene description (the only one that may ask for recognition); Meta is a stub.
REAL = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}
SCENE = {"text": "Una sala.", "mode": "meta", "model": "m", "latency_ms": 1}
FEATURE = {"embedding": VECTOR, "sharpness": 80, "box": [0, 0, 1, 1]}


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), "white").save(buffer, format="JPEG")
    return SimpleUploadedFile("face.jpg", buffer.getvalue(), "image/jpeg")


def jpeg():
    return photo().read()


class People:
    def make(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="face-owner", password="Test-only!Owner-63152"))
        self.relative = adult(users.create_user(username="face-relative"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Ficticia", face_recognition_enabled=True)
        self.member = Membership.objects.create(profile=self.profile, user=self.relative, relationship="Hija")
        self.profile = authorize(self.profile, camera_local=True, meta_photos=True, face_local=True)
        self.face = FamilyFace.objects.create(member=self.member, display_name="Familiar ficticio",
                                              embedding_encrypted=encrypt('{"version": 2, "samples": [%s]}' % VECTOR),
                                              expires_at=timezone.now() + timedelta(days=30))
        self.base = f"/api/v1/profiles/{self.profile.pk}/faces/"

    def scene(self):
        """Scene description on the real path with family recognition asked for (as continuous watching does)."""
        with patch.dict(os.environ, REAL), patch("assistance.views.describe_scene", return_value=dict(SCENE)), \
                patch("assistance.views.normalize_image", return_value=jpeg()):
            return self.as_user(self.owner).post("/api/v1/scene/", {"image": photo(), "locale": "es-EC", "profile": str(self.profile.pk),
                                                                     "family": "true"}, format="multipart")

    def as_user(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client


class DisabledByDefaultTests(People, TestCase):
    def setUp(self):
        self.make()
        os.environ.pop("AINGEL_FACE_RECOGNITION_ENABLED", None)
        # Any face processing fails the test at once.
        self.spies = [patch("care.faces.cv2.FaceDetectorYN.create", side_effect=AssertionError("face detector loaded")),
                      patch("care.faces.cv2.FaceRecognizerSF.create", side_effect=AssertionError("face recognizer loaded")),
                      patch("care.faces.normalize_image", side_effect=AssertionError("face image read"))]
        for spy in self.spies:
            spy.start()

    def tearDown(self):
        for spy in self.spies:
            spy.stop()

    def test_the_switch_is_off_unless_exactly_1(self):
        for value in (None, "0", "", "true", "yes", "1 "):
            with patch.dict(os.environ, {} if value is None else {"AINGEL_FACE_RECOGNITION_ENABLED": value}):
                with self.assertRaises(FaceRecognitionDisabled):
                    embeddings(jpeg())
                with self.assertRaises(FaceRecognitionDisabled):
                    family_matches(self.profile, jpeg())

    def test_no_route_processes_a_face(self):
        owner, relative = self.as_user(self.owner), self.as_user(self.relative)
        refused = [
            owner.post(self.base + "recognize/", {"image": photo(), "consent": "true"}),
            relative.post(self.base, {"image": [photo()], "display_name": "Yo", "consent": "true", "own_photo": "true"}),
            owner.post(self.base + "consent/", {"enabled": True, "consent": True, "password": "Test-only!Owner-63152"}, format="json"),
        ]
        for response in refused:
            self.assertEqual((response.status_code, response.data), (503, {"error": "face_recognition_disabled"}))
        self.assertFalse(AuditEvent.objects.filter(action__startswith="face.local_match").exists())

    def test_scene_description_never_reaches_recognition(self):
        with patch("assistance.views.family_matches", side_effect=AssertionError("recognition called")) as matches:
            response = self.scene()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["people"], [])
        matches.assert_not_called()

    def test_looking_and_withdrawing_keep_working_and_nothing_is_deleted_unasked(self):
        state = self.as_user(self.owner).get(self.base)
        self.assertEqual(state.status_code, 200)
        self.assertEqual((state.data["available"], state.data["enabled"], len(state.data["enrollments"])), (False, True, 1))
        self.assertTrue(FamilyFace.objects.filter(pk=self.face.pk).exists())  # still there after every refused call
        # The person's own face_local decision can still be withdrawn.
        self.assertIsNone(decide(self.profile, self.owner, "face_local", "revoke"))
        # A relative deletes their own enrollment when they ask.
        self.assertEqual(self.as_user(self.relative).delete(self.base).status_code, 204)
        self.assertFalse(FamilyFace.objects.filter(pk=self.face.pk).exists())
        # The owner can turn the feature off.
        off = self.as_user(self.owner).post(self.base + "consent/", {"enabled": False}, format="json")
        self.assertEqual((off.status_code, off.data), (200, {"enabled": False}))


@patch.dict(os.environ, {"AINGEL_FACE_RECOGNITION_ENABLED": "1"})
class RevocationDuringProcessingTests(People, TestCase):
    """For a future reactivation: the decision is checked before OpenCV runs and again after it."""

    def setUp(self):
        self.make()

    def recognize(self):
        with patch("care.faces.normalize_image", return_value=jpeg()):
            return self.as_user(self.owner).post(self.base + "recognize/", {"image": photo(), "consent": "true"})

    def test_a_match_is_returned_while_everything_is_authorized(self):
        with patch("care.faces.embeddings", return_value=[FEATURE]):
            response = self.recognize()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["faces"][0]["candidate"]["display_name"], "Familiar ficticio")

    def test_scene_names_the_relative_while_authorized(self):
        with patch("care.faces.embeddings", return_value=[FEATURE]):
            response = self.scene()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([p["display_name"] for p in response.data["people"]], ["Familiar ficticio"])

    def test_without_the_persons_grant_nothing_is_processed(self):
        decide(self.profile, self.owner, "face_local", "revoke")
        with patch("care.faces.embeddings") as processing:
            response = self.recognize()
        self.assertEqual(response.status_code, 400)
        processing.assert_not_called()

    def test_revocations_during_processing_discard_the_result(self):
        revocations = {
            "face_local grant": lambda: decide(self.profile, self.owner, "face_local", "revoke"),
            "camera grant": lambda: decide(self.profile, self.owner, "camera_local", "revoke"),
            "feature off": lambda: self.as_user(self.owner).post(self.base + "consent/", {"enabled": False}, format="json"),
        }
        for name, revoke in revocations.items():
            with self.subTest(name):
                self.make_fresh()

                def revoked_meanwhile(_image):
                    revoke()
                    return [FEATURE]

                with patch("care.faces.embeddings", side_effect=revoked_meanwhile):
                    response = self.recognize()
                self.assertEqual((response.status_code, response.data), (409, {"error": "face_consent_changed"}))
                self.assertFalse(AuditEvent.objects.filter(profile=self.profile, action="face.local_match_requested").exists())

    def make_fresh(self):
        Profile.objects.all().delete()
        get_user_model().objects.all().delete()
        self.make()

    def test_scene_names_no_one_when_revoked_during_processing(self):
        def revoked_meanwhile(_image):
            decide(self.profile, self.owner, "face_local", "revoke")
            return [FEATURE]

        with patch("care.faces.embeddings", side_effect=revoked_meanwhile) as processing:
            response = self.scene()
        processing.assert_called_once()  # recognition really ran on this path
        # Revoked while processing: no one is named (and the person's consent epoch also drops the description: 409).
        self.assertNotIn("people", response.data if response.status_code != 200 else {})
        self.assertEqual(response.data.get("people", []), [])
        self.assertNotIn("Familiar ficticio", str(response.content))


@patch.dict(os.environ, {"AINGEL_FACE_RECOGNITION_ENABLED": "1"})
class ConcurrentRevocationTests(People, TransactionTestCase):
    """A real second thread revokes while the first one is inside the face processing."""

    def setUp(self):
        self.make()

    def test_revocation_from_another_thread_while_opencv_runs(self):
        inside, released, outcome = threading.Event(), threading.Event(), {}

        def slow_processing(_image):
            inside.set()
            released.wait(10)
            return [FEATURE]

        def recognize():
            try:
                outcome["result"] = family_matches(Profile.objects.get(pk=self.profile.pk), jpeg())
            except FaceConsentChanged:
                outcome["result"] = "discarded"
            except Exception as error:  # surfaced in the assertion
                outcome["result"] = repr(error)

        with patch("care.faces.embeddings", side_effect=slow_processing):
            worker = threading.Thread(target=recognize)
            worker.start()
            self.assertTrue(inside.wait(10))
            # The person withdraws from their own device while the faces are being processed.
            self.assertIsNone(decide(Profile.objects.get(pk=self.profile.pk), self.owner, "face_local", "revoke"))
            released.set()
            worker.join(10)
        self.assertEqual(outcome["result"], "discarded")
