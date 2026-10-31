import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from care.models import AuditEvent, Membership, Profile
from care.testing import adult, authorize

META = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1"}
CONSENTS = {"camera": True, "microphone": True, "meta_data": True}


class AuditFixTests(TestCase):
    """Disconnections found by the 29-10-2026 audit."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="audit-owner"))
        self.caregiver = adult(users.create_user(username="audit-caregiver"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Owner", consents=CONSENTS)
        authorize(self.profile, CONSENTS)
        Membership.objects.create(profile=self.profile, user=self.caregiver, relationship="Hija", can_configure=True)
        self.client = APIClient()

    def test_only_the_person_changes_the_authorizations(self):
        path = f"/api/v1/profiles/{self.profile.pk}/"
        consent = path + "consent/"
        self.client.force_authenticate(self.caregiver)
        # The old coarse flags are gone from profile edits; decisions are the person's own, one purpose at a time.
        moved = self.client.patch(path, {"consents": {"camera": True, "microphone": True, "meta_data": False}}, format="json")
        self.assertEqual((moved.status_code, moved.data), (400, {"error": "consents_moved"}))
        refused = self.client.post(consent, {"purpose": "meta_photos", "decision": "revoke"}, format="json")
        self.assertEqual((refused.status_code, refused.data), (403, {"error": "consent_subject_only"}))
        self.assertEqual(self.client.patch(path, {"display_name": "Mamá"}, format="json").status_code, 200)
        self.client.force_authenticate(self.owner)
        decided = self.client.post(consent, {"purpose": "meta_photos", "decision": "revoke"}, format="json")
        self.assertEqual(decided.status_code, 200, decided.data)
        self.assertEqual({p["id"]: p["status"] for p in decided.data["purposes"]}["meta_photos"], "revoked")

    def test_an_invalid_action_alone_is_not_an_empty_answer(self):
        self.client.force_authenticate(self.owner)

        def fake(instructions, input_text, limit, web_search=False, functions=None, basis=None):
            return {"mode": "meta", "model": "muse-spark-1.3", "text": "", "action": {"name": "find_object", "arguments": {"object_name": "<b>"}}, "latency_ms": 5}

        with patch.dict(os.environ, META), patch("assistance.conversation.call_spark", fake), patch("assistance.conversation.best_topic", return_value=None):
            response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/conversation/",
                                        {"turns": [{"role": "user", "text": "Busca"}], "actions": ["find_object"]}, format="json")
        self.assertEqual((response.status_code, response.data), (503, {"error": "companion_empty_response"}))

    def test_companion_chat_works_with_the_sign_up_authorization_outside_test_mode(self):
        self.client.force_authenticate(self.owner)
        captured = {}

        def fake(rules, input_text, *args, **kwargs):
            captured.update(rules=rules, input=json.loads(input_text))
            return {"mode": "meta", "model": "muse-spark-1.3", "text": "Hola", "latency_ms": 5}

        with patch.dict(os.environ, {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}), patch("assistance.companion.call_spark", fake):
            response = self.client.post(f"/api/v1/profiles/{self.profile.pk}/companion/chat/", {"text": "¿Qué es la presión arterial?"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(captured["input"], {"question": "¿Qué es la presión arterial?"})
        self.assertNotIn("synthetic test", captured["rules"])
        self.assertTrue(AuditEvent.objects.filter(action="companion.chat").exists())
        authorize(self.profile, {**CONSENTS, "meta_data": False})
        with patch.dict(os.environ, {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}), patch("assistance.companion.call_spark", fake):
            refused = self.client.post(f"/api/v1/profiles/{self.profile.pk}/companion/chat/", {"text": "Hola"}, format="json")
        self.assertEqual(refused.data["error"], "privacy_review_required")
