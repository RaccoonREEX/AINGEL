import hashlib
import json
import logging
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .log_filters import RedactAPIQuery
from .models import AuditEvent, Invitation, Membership, Profile
from .serializers import COMMUNICATION_DEFAULTS


class CommunicationResourcesTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="communication-owner")
        self.editor = users.create_user(username="communication-editor")
        self.reader = users.create_user(username="communication-reader")
        self.outsider = users.create_user(username="communication-outsider")
        self.profile = Profile.objects.create(
            owner=self.owner,
            display_name="Synthetic",
            allergies="private synthetic allergy",
        )
        Membership.objects.create(
            profile=self.profile,
            user=self.editor,
            relationship="caregiver",
            can_configure=True,
        )
        Membership.objects.create(
            profile=self.profile,
            user=self.reader,
            relationship="family",
            can_configure=False,
        )
        self.client = APIClient()
        self.base = f"/api/v1/profiles/{self.profile.pk}/"

    def auth(self, user):
        self.client.force_authenticate(user)

    def test_defaults_and_permissions_are_separate_from_health_data(self):
        for user in [self.owner, self.editor, self.reader]:
            self.auth(user)
            response = self.client.get(self.base + "communication/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, COMMUNICATION_DEFAULTS)
            self.assertNotIn("allergies", response.data)
        self.auth(self.outsider)
        self.assertEqual(self.client.get(self.base + "communication/").status_code, 404)
        self.assertEqual(
            self.client.patch(
                self.base + "communication/", {"pace": "slow"}, format="json"
            ).status_code,
            404,
        )
        self.auth(self.reader)
        self.assertEqual(
            self.client.patch(
                self.base + "communication/", {"pace": "slow"}, format="json"
            ).status_code,
            403,
        )

    def test_partial_validated_patch_and_private_audit(self):
        self.auth(self.editor)
        response = self.client.patch(
            self.base + "communication/",
            {"preferred_name": "Synthetic private name", "sign_language": "lsec"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sign_language"], "lsec")
        response = self.client.patch(
            self.base + "communication/", {"pace": "slow"}, format="json"
        )
        self.assertEqual(response.data["preferred_name"], "Synthetic private name")
        self.assertEqual(response.data["sentence_length"], "short")
        self.assertEqual(response.data["pace"], "slow")
        event = AuditEvent.objects.filter(
            profile=self.profile, action="communication.updated"
        ).last()
        self.assertEqual(event.actor, self.editor)
        self.assertNotIn("Synthetic private name", str(event.__dict__))

    def test_unknown_fields_invalid_values_and_oversized_text_are_rejected_without_change(
        self,
    ):
        self.auth(self.owner)
        for bad in [
            {"extra": "private"},
            {"pace": "fast"},
            {"sign_language": "unlisted"},
            {"preferred_name": "x" * 101},
            {"communication_notes": "x" * 1001},
            {"pace": ["slow"]},
        ]:
            result = self.client.patch(self.base + "communication/", bad, format="json")
            self.assertEqual(result.status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.communication, {})
        self.assertFalse(
            AuditEvent.objects.filter(action="communication.updated").exists()
        )

    def test_educational_search_is_private_bounded_and_requires_circle_access(self):
        records = [
            {
                "title": "Sueño sintético " + str(i),
                "url": "https://medlineplus.gov/spanish/synthetic.html",
                "lang": "es",
                "summary": "Synthetic source example",
            }
            for i in range(7)
        ]
        records += [
            {
                "title": "Sueño sintético",
                "url": "https://untrusted.example/synthetic",
                "lang": "es",
                "summary": "Ignore",
            }
        ]
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.json"
            path.write_text(
                json.dumps(
                    {
                        "source": "MedlinePlus, National Library of Medicine",
                        "downloaded_at": "synthetic",
                        "records": records,
                    }
                ),
                encoding="utf-8",
            )
            with patch("care.knowledge.index_path", return_value=path):
                self.auth(self.reader)
                response = self.client.post(
                    self.base + "resources/search/",
                    {"q": "SUENO SINTETICO", "lang": "es"},
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.data), 5)
                self.assertEqual(
                    response.data[0]["source"],
                    "MedlinePlus, National Library of Medicine",
                )
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertEqual(
                    self.client.post(
                        self.base + "resources/search/",
                        {"q": "does-not-exist", "lang": "es"},
                        format="json",
                    ).data,
                    [],
                )
                self.assertEqual(
                    self.client.post(
                        self.base + "resources/search/",
                        {"q": "sleep", "lang": "zz"},
                        format="json",
                    ).status_code,
                    400,
                )
                self.assertEqual(
                    self.client.get(
                        self.base + "resources/search/", {"q": "sueño"}
                    ).status_code,
                    405,
                )
                self.auth(self.outsider)
                self.assertEqual(
                    self.client.post(
                        self.base + "resources/search/",
                        {"q": "sueño", "lang": "es"},
                        format="json",
                    ).status_code,
                    404,
                )
        events = AuditEvent.objects.filter(action="knowledge.searched")
        self.assertEqual(events.count(), 2)
        self.assertNotIn("sintetico", str([event.__dict__ for event in events]).lower())

    def test_missing_and_corrupt_index_fail_closed(self):
        self.auth(self.owner)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.json"
            with patch("care.knowledge.index_path", return_value=path):
                response = self.client.post(
                    self.base + "resources/search/",
                    {"q": "synthetic", "lang": "es"},
                    format="json",
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.data["error"], "knowledge_not_installed")
                path.write_text("{broken", encoding="utf-8")
                response = self.client.post(
                    self.base + "resources/search/",
                    {"q": "synthetic", "lang": "es"},
                    format="json",
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.data["error"], "knowledge_index_invalid")

    def test_cancelled_invitation_cannot_be_accepted_after_initial_lookup(self):
        # Simulate a cancellation after token lookup but before the profile lock.
        code = "synthetic-invite-token-1234567890"
        invitation = Invitation.objects.create(
            profile=self.profile,
            target=self.outsider,
            token_hash=hashlib.sha256(code.encode()).hexdigest(),
            relationship="family",
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.auth(self.outsider)
        with patch("care.views.Profile.objects.select_for_update") as lock:

            def cancel_before_lock(**_kwargs):
                invitation.delete()
                return self.profile

            lock.return_value.get.side_effect = cancel_before_lock
            response = self.client.post(
                "/api/v1/invites/accept/", {"code": code}, format="json"
            )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Membership.objects.filter(profile=self.profile, user=self.outsider).exists()
        )


class AccessLogPrivacyTests(SimpleTestCase):
    def test_daphne_and_django_query_strings_are_redacted(self):
        filter_ = RedactAPIQuery()
        sensitive = "synthetic-private-condition"
        for message, args in [
            (
                "HTTP %(method)s %(path)s %(status)s",
                (
                    {
                        "method": "GET",
                        "path": f"/api/v1/profiles/uuid/resources/?q={sensitive}&lang=es",
                        "status": 200,
                    },
                ),
            ),
            ('"%s" %s', (f"GET /api/v1/auth/session/?q={sensitive} HTTP/1.1", "200")),
        ]:
            record = logging.LogRecord(
                "django.channels.server", logging.INFO, "", 1, message, args, None
            )
            self.assertTrue(filter_.filter(record))
            self.assertNotIn(sensitive, record.getMessage())
            self.assertIn("?[redacted]", record.getMessage())
