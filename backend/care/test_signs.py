import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from .models import AuditEvent, Membership, Profile


class ReviewedSignsTests(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = users.create_user(username="signs-owner")
        self.family = users.create_user(username="signs-family")
        self.outsider = users.create_user(username="signs-outsider")
        self.profile = Profile.objects.create(
            owner=self.owner, display_name="Synthetic"
        )
        Membership.objects.create(
            profile=self.profile,
            user=self.family,
            relationship="family",
            can_configure=False,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.base = f"/api/v1/profiles/{self.profile.pk}/signs/"
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patcher = patch("care.signs.sign_root", return_value=self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def install_fixture(self):
        # A tiny synthetic ISO-BMFF header, used only to test transport and integrity.
        # It is not an actual playable video or a sign-language translation.
        video = b"\x00\x00\x00\x10ftypisom\x00\x00\x00\x00"
        digest = hashlib.sha256(video).hexdigest()
        (self.root / "clips").mkdir(exist_ok=True)
        (self.root / "clips" / (digest + ".mp4")).write_bytes(video)
        self.clip = {
            "id": "synthetic-phrase",
            "language": "lsec",
            "text": "¿Dónde está el baño?",
            "filename": digest + ".mp4",
            "sha256": digest,
            "reviewed": True,
            "reviewer": "Synthetic reviewer",
            "reviewed_at": "2026-10-27",
            "source": "Synthetic test source",
            "attribution": "Synthetic test attribution",
            "license": "Synthetic testing only",
            "source_url": "https://example.org/synthetic-source",
        }
        self.write_catalog([self.clip])
        return video

    def write_catalog(self, clips):
        (self.root / "catalog.json").write_text(
            json.dumps({"version": 1, "clips": clips}), encoding="utf-8"
        )

    def lookup(self, phrase, language="lsec"):
        return self.client.post(
            self.base + "lookup/", {"text": phrase, "language": language}, format="json"
        )

    def test_empty_catalog_does_not_fabricate_translation(self):
        response = self.lookup("synthetic speech")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"available": False})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertFalse(AuditEvent.objects.exists())

    def test_only_whole_phrase_in_the_selected_language_matches(self):
        video = self.install_fixture()
        response = self.lookup("  ¿DÓNDE  ESTÁ EL BAÑO?  ")
        self.assertTrue(response.data["available"])
        self.assertEqual(response.data["clip"]["id"], "synthetic-phrase")
        self.assertEqual(
            response.data["clip"]["attribution"], "Synthetic test attribution"
        )
        self.assertNotIn("text", response.data["clip"])
        for phrase, language in [
            ("baño", "lsec"),
            ("¿Dónde está el baño?", "asl"),
            ("¿Donde esta el baño?", "lsec"),
            ("¿No está el baño?", "lsec"),
        ]:
            self.assertEqual(self.lookup(phrase, language).data, {"available": False})
        clip = self.client.get(self.base + "clips/synthetic-phrase/")
        self.assertEqual(clip.status_code, 200)
        self.assertEqual(clip["Content-Type"], "video/mp4")
        self.assertEqual(clip["Cache-Control"], "no-store")
        self.assertEqual(clip.content, video)
        self.assertFalse(AuditEvent.objects.exists())

    def test_authentication_profile_isolation_and_readonly_caregiver(self):
        self.install_fixture()
        anonymous = APIClient()
        self.assertEqual(
            anonymous.get(self.base + "clips/synthetic-phrase/").status_code, 403
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.lookup("¿Dónde está el baño?").status_code, 404)
        self.assertEqual(
            self.client.get(self.base + "clips/synthetic-phrase/").status_code, 404
        )
        self.client.force_authenticate(self.family)
        self.assertTrue(self.lookup("¿Dónde está el baño?").data["available"])
        self.assertEqual(
            self.client.get(self.base + "clips/synthetic-phrase/").status_code, 200
        )

    def test_unreviewed_missing_provenance_duplicate_or_unsafe_paths_rejected(self):
        self.install_fixture()
        cases = [
            {**self.clip, "reviewed": False},
            {**self.clip, "reviewer": ""},
            {**self.clip, "attribution": ""},
            {**self.clip, "source_url": "http://example.org/"},
            {**self.clip, "source_url": "https://user:pass@example.org/"},
            {**self.clip, "source_url": "https://example.org:invalid/"},
            {**self.clip, "video_url": "https://example.org/remote.mp4"},
            {**self.clip, "language": "other"},
            {**self.clip, "filename": "../../private.mp4"},
            {**self.clip, "reviewed_at": "invalid"},
        ]
        for invalid in cases:
            self.write_catalog([invalid])
            self.assertEqual(self.lookup("¿Dónde está el baño?").status_code, 503)
        self.write_catalog([self.clip, {**self.clip, "id": "another"}])
        self.assertEqual(self.lookup("¿Dónde está el baño?").status_code, 503)
        self.assertFalse(AuditEvent.objects.exists())

    def test_integrity_checked_again_when_served_and_no_traversal(self):
        self.install_fixture()
        self.assertTrue(self.lookup("¿Dónde está el baño?").data["available"])
        (self.root / "clips" / self.clip["filename"]).write_bytes(
            b"\x00\x00\x00\x10ftypxxxx\x00\x00\x00\x00"
        )
        self.assertEqual(
            self.client.get(self.base + "clips/synthetic-phrase/").status_code, 503
        )
        self.assertEqual(self.lookup("¿Dónde está el baño?").status_code, 503)
        self.assertEqual(
            self.client.get(self.base + "clips/..%5Csecret/").status_code, 404
        )

    def test_bad_requests_and_oversized_clip_fail_closed(self):
        self.install_fixture()
        self.assertEqual(self.lookup(" ").status_code, 400)
        self.assertEqual(self.lookup("hello", "none").status_code, 400)
        self.assertEqual(self.lookup("hello", "other").status_code, 400)
        self.assertEqual(self.lookup("x" * 301).status_code, 400)
        with patch("care.signs.MAX_CLIP_BYTES", 8):
            self.assertEqual(self.lookup("¿Dónde está el baño?").status_code, 503)
        self.assertEqual(
            self.client.get(self.base + "clips/unknown-id/").status_code, 404
        )
