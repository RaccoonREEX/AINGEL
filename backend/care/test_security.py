from datetime import timedelta
import io
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from PIL import Image
import pyotp
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from .crypto import decrypt, encrypt
from .faces import candidate_match
from .models import FamilyFace, MFADevice, Membership, Profile


class MFATests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="mfa-user", password="Test-Only!Mfa-82714"
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.token = self.client.get("/api/v1/auth/session/").json()["csrf"]

    def post(self, url, data):
        result = self.client.post(
            "/api/v1/auth/" + url, data, format="json", HTTP_X_CSRFTOKEN=self.token
        )
        if result.status_code == 200 and "csrf" in result.json():
            self.token = result.json()["csrf"]
        return result

    def login(self):
        return self.post(
            "login/", {"username": "mfa-user", "password": "Test-Only!Mfa-82714"}
        )

    def device(self):
        secret = pyotp.random_base32()
        return (
            MFADevice.objects.create(
                user=self.user, secret_encrypted=encrypt(secret), enabled=True, epoch=1
            ),
            secret,
        )

    def test_password_is_not_enough_when_mfa_enabled(self):
        device, secret = self.device()
        result = self.login()
        self.assertTrue(result.json()["mfa_required"])
        self.assertIsNone(self.client.get("/api/v1/auth/session/").json()["user"])
        self.assertEqual(self.client.get("/api/v1/profiles/").status_code, 403)
        verified = self.post("mfa/verify/", {"code": pyotp.TOTP(secret).now()})
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.json()["user"]["username"], "mfa-user")
        self.assertEqual(self.client.get("/api/v1/profiles/").status_code, 200)
        self.assertNotEqual(device.secret_encrypted, secret)

    def test_totp_cannot_be_replayed_after_new_password_challenge(self):
        device, secret = self.device()
        self.login()
        code = pyotp.TOTP(secret).now()
        self.assertEqual(self.post("mfa/verify/", {"code": code}).status_code, 200)
        self.post("logout/", {})
        self.login()
        self.assertEqual(self.post("mfa/verify/", {"code": code}).status_code, 400)

    def test_mfa_setup_confirm_recovery_single_use_and_disable(self):
        self.login()
        wrong = self.post("mfa/setup/", {"password": "wrong"})
        self.assertEqual(wrong.status_code, 403)
        result = self.post("mfa/setup/", {"password": "Test-Only!Mfa-82714"})
        secret = result.data["secret"]
        self.assertTrue(result.data["qr_png"].startswith("data:image/png;base64,"))
        device = MFADevice.objects.get(user=self.user)
        self.assertFalse(device.enabled)
        self.assertNotEqual(device.pending_encrypted, secret)
        result = self.post("mfa/enable/", {"code": pyotp.TOTP(secret).now()})
        self.assertEqual(result.status_code, 200)
        codes = result.data["recovery_codes"]
        self.assertEqual(len(codes), 8)
        device.refresh_from_db()
        self.assertNotIn(codes[0], str(device.recovery_hashes))
        self.post("logout/", {})
        self.login()
        self.assertEqual(self.post("mfa/verify/", {"code": codes[0]}).status_code, 200)
        self.post("logout/", {})
        self.login()
        self.assertEqual(self.post("mfa/verify/", {"code": codes[0]}).status_code, 400)
        self.assertEqual(self.post("mfa/verify/", {"code": codes[1]}).status_code, 200)
        response = self.post(
            "mfa/disable/", {"password": "Test-Only!Mfa-82714", "code": codes[2]}
        )
        self.assertEqual(response.status_code, 200)
        device.refresh_from_db()
        self.assertFalse(device.enabled)
        self.assertEqual(device.secret_encrypted, "")

    def test_expired_challenge_and_attempt_limit(self):
        self.device()
        self.login()
        session = self.client.session
        session["mfa_pending_until"] = int(time.time()) - 1
        session.save()
        self.assertEqual(self.post("mfa/verify/", {"code": "000000"}).status_code, 400)
        self.login()
        for _ in range(6):
            self.assertEqual(
                self.post("mfa/verify/", {"code": "not-valid"}).status_code, 400
            )
        self.assertEqual(
            self.post("mfa/verify/", {"code": "not-valid"}).status_code, 429
        )

    def test_enabling_mfa_invalidates_preexisting_other_session(self):
        other = APIClient()
        other.force_login(self.user)
        self.login()
        setup = self.post("mfa/setup/", {"password": "Test-Only!Mfa-82714"})
        self.assertEqual(
            self.post(
                "mfa/enable/", {"code": pyotp.TOTP(setup.data["secret"]).now()}
            ).status_code,
            200,
        )
        self.assertEqual(other.get("/api/v1/profiles/").status_code, 403)


def photo():
    data = io.BytesIO()
    Image.new("RGB", (128, 128), "white").save(data, format="PNG")
    return SimpleUploadedFile("synthetic.png", data.getvalue(), "image/png")


class FamilyFaceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user(
            username="owner", password="Test-only!Owner-63152"
        )
        self.family = get_user_model().objects.create_user(username="family")
        self.outsider = get_user_model().objects.create_user(username="stranger")
        self.profile = Profile.objects.create(
            owner=self.owner, display_name="Synthetic profile"
        )
        self.member = Membership.objects.create(
            profile=self.profile, user=self.family, relationship="Synthetic family"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = f"/api/v1/profiles/{self.profile.pk}/faces/"

    def enable(self):
        response = self.client.post(
            self.base + "consent/",
            {"enabled": True, "consent": True, "password": "Test-only!Owner-63152"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_default_disabled_and_caregiver_cannot_enable(self):
        self.assertFalse(self.client.get(self.base).data["enabled"])
        self.client.force_authenticate(self.family)
        self.assertEqual(
            self.client.post(self.base + "consent/", {"enabled": True}).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                self.base,
                {
                    "image": photo(),
                    "display_name": "Test",
                    "consent": "true",
                    "own_photo": "true",
                },
            ).status_code,
            400,
        )

    def test_owner_cannot_enroll_another_person_by_uploading_their_face(self):
        self.enable()
        self.assertEqual(
            self.client.post(
                self.base,
                {
                    "image": photo(),
                    "display_name": "Test",
                    "consent": "true",
                    "own_photo": "true",
                },
            ).status_code,
            403,
        )

    @patch(
        "care.faces.embeddings",
        return_value=[{"embedding": [1.0] + [0.0] * 127, "box": [0, 0, 1, 1]}],
    )
    def test_self_consent_encryption_and_revocation(self, _):
        self.enable()
        self.client.force_authenticate(self.family)
        self.assertEqual(
            self.client.post(
                self.base, {"image": photo(), "display_name": "Test"}
            ).status_code,
            400,
        )
        response = self.client.post(
            self.base,
            {
                "image": photo(),
                "display_name": "Family test",
                "consent": "true",
                "own_photo": "true",
            },
        )
        self.assertEqual(response.status_code, 201)
        face = FamilyFace.objects.get()
        self.assertNotIn("embedding", response.data)
        self.assertNotEqual(face.embedding_encrypted, decrypt(face.embedding_encrypted))
        self.assertEqual(self.client.delete(self.base).status_code, 204)
        self.assertEqual(FamilyFace.objects.count(), 0)

    @patch("care.faces.embeddings", return_value=[])
    def test_no_face_cannot_create_an_enrollment(self, _):
        self.enable()
        self.client.force_authenticate(self.family)
        result = self.client.post(
            self.base,
            {
                "image": photo(),
                "display_name": "Family test",
                "consent": "true",
                "own_photo": "true",
            },
        )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(FamilyFace.objects.exists())

    def test_disabling_or_revoking_membership_deletes_templates(self):
        self.enable()
        FamilyFace.objects.create(
            member=self.member,
            display_name="Family",
            embedding_encrypted=encrypt("[]"),
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.client.post(self.base + "consent/", {"enabled": False}, format="json")
        self.assertFalse(FamilyFace.objects.exists())
        self.enable()
        FamilyFace.objects.create(
            member=self.member,
            display_name="Family",
            embedding_encrypted=encrypt("[]"),
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.member.delete()
        self.assertFalse(FamilyFace.objects.exists())

    def test_matching_rejects_unknown_and_ambiguous_candidates(self):
        vector = [1.0] + [0.0] * 127
        other = [0.0, 1.0] + [0.0] * 126
        self.assertIsNone(candidate_match(vector, []))
        self.assertIsNone(candidate_match(vector, [{"embedding": other}]))
        self.assertIsNone(
            candidate_match(vector, [{"embedding": vector}, {"embedding": vector}])
        )
        match = {"id": "synthetic", "embedding": vector}
        self.assertEqual(candidate_match(vector, [match])["id"], "synthetic")

    def test_recognition_only_owner_and_explicit_capture_consent(self):
        self.enable()
        self.assertEqual(
            self.client.post(self.base + "recognize/", {"image": photo()}).status_code,
            400,
        )
        self.client.force_authenticate(self.family)
        self.assertEqual(
            self.client.post(
                self.base + "recognize/", {"image": photo(), "consent": "true"}
            ).status_code,
            403,
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.base).status_code, 404)
