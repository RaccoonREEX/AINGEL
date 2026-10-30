import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from care.models import AuditEvent, Profile

VOCABULARY = {"tu": "tú / you", "bien": "bien / good", "pregunta": "¿pregunta? / question?", "yo": "yo / I", "comer": "comer / eat"}
META = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1"}


class GlossTests(TestCase):
    """«¿Qué tal?» is signed by meaning (29-10-2026: «cómo estás» had been signed «comer»)."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = users.create_user(username="gloss-owner")
        self.profile = Profile.objects.create(owner=self.owner, display_name="Owner", consents={"camera": True, "microphone": True, "meta_data": True})
        self.path = f"/api/v1/profiles/{self.profile.pk}/signs/gloss/"
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post(self, signs, text="¿Qué tal?", env=META, vocabulary=VOCABULARY):
        captured = {}

        def fake(instructions, input_text, limit, web_search=False, functions=None):
            captured.update(instructions=instructions, input=input_text, functions=functions)
            return {"mode": "meta", "model": "muse-spark-1.3", "text": "", "action": {"name": "sign_sequence", "arguments": {"signs": signs}}, "latency_ms": 5}

        with patch.dict(os.environ, env), patch("assistance.gloss.call_spark", fake):
            response = self.client.post(self.path, {"text": text, "vocabulary": vocabulary}, format="json")
        return response, captured

    def test_meaning_comes_back_as_known_signs_and_spelled_names(self):
        response, captured = self.post(["tu", "bien", "pregunta"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["gloss"], [{"sign": "tu"}, {"sign": "bien"}, {"sign": "pregunta"}])
        self.assertEqual(captured["input"], "¿Qué tal?")
        self.assertIn("pregunta: ¿pregunta? / question?", captured["instructions"])
        self.assertIn("pending validation with Deaf LSEC signers", captured["instructions"])
        self.assertEqual(set(captured["functions"]), {"sign_sequence"})
        named, _ = self.post(["yo", "spell:Ramírez"], text="Soy Ramírez")
        self.assertEqual(named.data["gloss"], [{"sign": "yo"}, {"spell": "ramirez"}])
        self.assertEqual(AuditEvent.objects.filter(action="signs.gloss").count(), 2)

    def test_invented_signs_reject_the_whole_answer(self):
        for signs in (["tu", "feliz"], ["spell:<b>"], [], "tu bien"):
            response, _ = self.post(signs)
            self.assertEqual(response.status_code, 503, signs)
            self.assertEqual(response.data["error"], "gloss_invalid")

    def test_requests_are_bounded_and_need_meta_and_sign_up_authorization(self):
        bad = [{"text": "", "vocabulary": VOCABULARY}, {"text": "x" * 301, "vocabulary": VOCABULARY},
               {"text": "Hola", "vocabulary": {"Bad Id": "x"}}, {"text": "Hola", "vocabulary": {"tu": "<script>"}},
               {"text": "Hola", "vocabulary": VOCABULARY, "extra": 1}]
        for body in bad:
            self.assertEqual(self.client.post(self.path, body, format="json").status_code, 400, body)
        response, _ = self.post(["tu"], env={"AINGEL_AI_MODE": "mock"})
        self.assertEqual(response.status_code, 503)
        self.profile.consents = {"camera": True, "microphone": True, "meta_data": False}
        self.profile.save()
        response, captured = self.post(["tu"])
        self.assertEqual(response.data["error"], "privacy_review_required")
        self.assertEqual(captured, {})
