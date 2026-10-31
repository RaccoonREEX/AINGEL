import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from care.models import AuditEvent, Membership, Profile
from care.testing import adult, authorize

from . import synthetic

TOPIC = {
    "title": "Synthetic source title",
    "lang": "es",
    "url": "https://medlineplus.gov/spanish/synthetic.html",
    "summary": "Synthetic example only. No patient data.",
    "source": "MedlinePlus, National Library of Medicine",
    "downloaded_at": "synthetic-date",
}


class CompanionTests(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="companion-owner"))
        self.reader = adult(users.create_user(username="companion-reader"))
        self.outsider = adult(users.create_user(username="companion-outsider"))
        self.profile = Profile.objects.create(
            owner=self.owner,
            display_name="PRIVATE_PROFILE_MARKER",
            allergies="PRIVATE_ALLERGY_MARKER",
            support_notes="PRIVATE_NOTES_MARKER",
            communication={
                "addressing": "formal",
                "pace": "slow",
                "preferred_name": "PRIVATE_NAME_MARKER",
                "communication_notes": "PRIVATE_COMMUNICATION_MARKER",
            },
        )
        Membership.objects.create(
            profile=self.profile,
            user=self.reader,
            relationship="family",
            can_configure=False,
        )
        self.path = f"/api/v1/profiles/{self.profile.pk}/companion/chat/"
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def post(self, **data):
        return self.client.post(self.path, data, format="json")

    def authorize_real(self, **purposes):
        # The owner is the person and grants sending their questions (fictitious markers only).
        authorize(self.profile, meta_conversation=True, **purposes)

    def test_authentication_scope_and_mock_mode_are_explicit(self):
        self.assertEqual(
            APIClient()
            .post(self.path, {"text": "Synthetic"}, format="json")
            .status_code,
            403,
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.post(text="Synthetic").status_code, 404)
        self.client.force_authenticate(self.reader)
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}):
            response = self.post(text="Synthetic question")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "mock")
        self.assertIsNone(response.data["model"])
        self.assertIsNone(response.data["source"])
        self.assertIn("no se generó", response.data["text"])
        self.assertEqual(response["Cache-Control"], "no-store")
        # Unauthorized free text only reaches the local test mode, recorded as such.
        self.assertTrue(AuditEvent.objects.filter(action="companion.local_test").exists())

    def test_synthetic_declaration_is_refused_and_bounded_single_request(self):
        meta = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}
        with patch.dict(os.environ, meta), patch("assistance.companion.httpx.Client") as provider:
            # Meta mode without the person's authorization: free text is refused before anything is built.
            cache.clear()
            response = self.client.post(self.path, {"text": "Synthetic"}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["error"], "privacy_review_required")
            # A client declaring its text synthetic proves nothing, whatever the value.
            for flag in (True, False, 1):
                cache.clear()
                response = self.client.post(self.path, {"text": "Synthetic", "synthetic": flag}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"], "synthetic_fixture_required")
            # Free content or a topic next to a fixture is refused; so is an unknown fixture.
            for value, error in (
                ({"fixture": "greeting", "text": "PRIVATE_TEXT_MARKER"}, "synthetic_fixture_only"),
                ({"fixture": "greeting", "topic_title": "x", "topic_lang": "es"}, "synthetic_fixture_only"),
                ({"fixture": "PRIVATE_TEXT_MARKER"}, "synthetic_fixture_invalid"),
                ({"fixture": ["greeting"]}, "synthetic_fixture_invalid"),
                ({"fixture": "greeting", "synthetic": True}, "synthetic_fixture_required"),
            ):
                cache.clear()
                response = self.client.post(self.path, value, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"], error)
            cache.clear()
            response = self.client.post(self.path, {"fixture": "greeting", "locale": "fr-FR"}, format="json")
            self.assertEqual(response.status_code, 400)
            provider.assert_not_called()
        # The person's authorized path is still a single bounded request.
        self.authorize_real()
        invalid = [
            {"text": " "},
            {"text": "x" * 1001},
            {"text": ["synthetic"]},
            {"text": "Synthetic", "history": ["PRIVATE"]},
            {"text": "Synthetic", "locale": "en-US"},
        ]
        with patch.dict(os.environ, {**meta, "AINGEL_REAL_DATA": "1"}), patch("assistance.companion.httpx.Client") as provider:
            for value in invalid:
                cache.clear()
                self.assertEqual(
                    self.client.post(self.path, value, format="json").status_code, 400
                )
            provider.assert_not_called()

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "0",
        },
    )
    @patch("assistance.companion.httpx.Client")
    def test_server_privacy_gate_stops_provider(self, provider):
        response = self.post(text="Synthetic")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "privacy_review_required")
        response = self.post(fixture="greeting")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "synthetic_tests_disabled")
        response = self.post(text="Synthetic", synthetic=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "synthetic_fixture_required")
        provider.assert_not_called()

    def test_source_must_be_selected_exactly_and_cannot_be_invented(self):
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}):
            self.assertEqual(
                self.post(
                    text="Synthetic", topic_title="Only title"
                ).status_code,
                400,
            )
            with patch("assistance.companion.exact_topic", return_value=None) as lookup:
                response = self.post(
                    text="Synthetic",
                    topic_title="Unlisted topic",
                    topic_lang="es",
                )
                self.assertEqual(response.status_code, 404)
                lookup.assert_called_once_with("Unlisted topic", "es")
            with patch("assistance.companion.exact_topic", return_value=TOPIC):
                response = self.post(
                    text="Synthetic",
                    topic_title=TOPIC["title"],
                    topic_lang="es",
                )
                self.assertEqual(response.data["source"]["title"], TOPIC["title"])
                self.assertEqual(response.data["source"]["url"], TOPIC["url"])
                self.assertNotIn("summary", response.data["source"])

    def test_real_index_requires_exact_valid_source_and_handles_missing_index(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "medlineplus.json"
            with patch("care.knowledge.index_path", return_value=path):
                response = self.post(
                    text="Synthetic",
                    topic_title=TOPIC["title"],
                    topic_lang="es",
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.data["error"], "knowledge_not_installed")
                path.write_text(
                    json.dumps(
                        {
                            "source": TOPIC["source"],
                            "downloaded_at": TOPIC["downloaded_at"],
                            "records": [TOPIC],
                        }
                    ),
                    encoding="utf-8",
                )
                with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}):
                    response = self.post(
                        text="Synthetic",
                        topic_title=TOPIC["title"],
                        topic_lang="es",
                    )
                    self.assertEqual(response.data["source"]["title"], TOPIC["title"])
                    response = self.post(
                        text="Synthetic",
                        topic_title="Synthetic source",
                        topic_lang="es",
                    )
                    self.assertEqual(response.status_code, 404)
                    path.write_text(
                        json.dumps(
                            {
                                "source": TOPIC["source"],
                                "downloaded_at": TOPIC["downloaded_at"],
                                "records": [
                                    {
                                        **TOPIC,
                                        "url": "https://medlineplus.gov:9999/synthetic",
                                    }
                                ],
                            }
                        ),
                        encoding="utf-8",
                    )
                    response = self.post(
                        text="Synthetic",
                        topic_title=TOPIC["title"],
                        topic_lang="es",
                    )
                    self.assertEqual(response.status_code, 404)

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"})
    def test_per_user_chat_rate_is_bounded(self):
        for _ in range(6):
            self.assertEqual(
                self.post(text="Synthetic").status_code, 200
            )
        self.assertEqual(self.post(text="Synthetic").status_code, 429)
        # Fixtures share the same per-user bound.
        self.assertEqual(self.post(fixture="greeting").status_code, 429)

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
            "AINGEL_REAL_DATA": "1",
        },
    )
    @patch("assistance.companion.httpx.Client")
    @patch("assistance.companion.exact_topic", return_value=TOPIC)
    def test_meta_payload_uses_only_allowed_settings_and_one_selected_public_source(
        self, _lookup, client
    ):
        self.authorize_real()
        stream = (
            client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
        )
        stream.iter_bytes.return_value = [
            json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "Synthetic response."}
                            ],
                        }
                    ],
                }
            ).encode()
        ]
        response = self.post(
            text="Synthetic question",
            topic_title=TOPIC["title"],
            topic_lang="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "meta")
        self.assertEqual(response.data["text"], "Synthetic response.")
        call = client.return_value.__enter__.return_value.stream.call_args
        self.assertEqual(call.args[:2], ("POST", "https://api.meta.ai/v1/responses"))
        payload = call.kwargs["json"]
        self.assertEqual(payload["model"], "muse-spark-1.3")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["input"][0]["role"], "user")
        self.assertIn("Never diagnose", payload["instructions"])
        self.assertIn('"pace": "slow"', payload["instructions"])
        self.assertIn(
            "Synthetic example only", payload["input"][0]["content"][0]["text"]
        )
        sent = json.loads(payload["input"][0]["content"][0]["text"])
        self.assertEqual(sent["question"], "Synthetic question")
        self.assertNotIn("synthetic_question", sent)
        for marker in [
            "PRIVATE_PROFILE_MARKER",
            "PRIVATE_ALLERGY_MARKER",
            "PRIVATE_NOTES_MARKER",
            "PRIVATE_NAME_MARKER",
            "PRIVATE_COMMUNICATION_MARKER",
        ]:
            self.assertNotIn(marker, json.dumps(payload))
        event = AuditEvent.objects.get(action="companion.chat")
        self.assertNotIn("Synthetic question", str(event.__dict__))
        self.assertNotIn("Synthetic response", str(event.__dict__))

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.companion.httpx.Client")
    @patch("assistance.companion.exact_topic", return_value=TOPIC)
    def test_fixture_payload_is_server_written_and_never_reads_the_profile(self, lookup, client):
        stream = (
            client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
        )
        stream.iter_bytes.return_value = [
            json.dumps(
                {
                    "status": "completed",
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "Synthetic response."}]}
                    ],
                }
            ).encode()
        ]
        response = self.post(fixture="hydration", locale="en-US")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "meta")
        self.assertEqual(response.data["synthetic_fixture"], "hydration")
        self.assertIsNone(response.data["source"])
        lookup.assert_not_called()
        payload = client.return_value.__enter__.return_value.stream.call_args.kwargs["json"]
        sent = json.loads(payload["input"][0]["content"][0]["text"])
        self.assertEqual(sent, {"synthetic_question": synthetic.QUESTIONS["hydration"]["en-US"]})
        self.assertIn("synthetic test", payload["instructions"])
        self.assertIn("Respond in English", payload["instructions"])
        # The fictitious profile's style, not this person's (their pace is slow and address formal).
        self.assertIn(json.dumps(synthetic.FICTIONAL_PREFERENCES, ensure_ascii=True), payload["instructions"])
        self.assertNotIn('"pace": "slow"', payload["instructions"])
        self.assertNotIn('"addressing": "formal"', payload["instructions"])
        for marker in [
            "PRIVATE_PROFILE_MARKER",
            "PRIVATE_ALLERGY_MARKER",
            "PRIVATE_NOTES_MARKER",
            "PRIVATE_NAME_MARKER",
            "PRIVATE_COMMUNICATION_MARKER",
        ]:
            self.assertNotIn(marker, json.dumps(payload))
        event = AuditEvent.objects.get(action="companion.synthetic_chat")
        self.assertNotIn("Synthetic response", str(event.__dict__))

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.companion.httpx.Client")
    def test_provider_failure_is_sanitized(self, client):
        client.return_value.__enter__.return_value.stream.side_effect = (
            httpx.ConnectError("PRIVATE_PROVIDER_RESPONSE")
        )
        response = self.post(fixture="greeting")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data, {"error": "companion_unavailable"})
        self.assertNotIn("PRIVATE_PROVIDER_RESPONSE", str(response.data))

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "synthetic-key",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.companion.httpx.Client")
    def test_incomplete_empty_and_excessive_provider_outputs_are_not_success(
        self, client
    ):
        stream = (
            client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
        )
        bodies = [
            ({"status": "incomplete", "output": []}, "companion_incomplete"),
            ({"status": "completed", "output": []}, "companion_empty_response"),
            (
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": "x" * 4001}],
                        }
                    ],
                },
                "companion_output_too_large",
            ),
        ]
        for body, error in bodies:
            stream.iter_bytes.return_value = [json.dumps(body).encode()]
            cache.clear()
            response = self.post(fixture="greeting")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.data["error"], error)


class WebSearchReplyTests(TestCase):
    """Shape of a Meta Responses reply with web_search (observed 29-10-2026): commentary, search, final answer."""

    @patch.dict(os.environ, {"MODEL_API_KEY": "synthetic-key"})
    @patch("assistance.companion.httpx.Client")
    def test_only_the_answer_is_kept_with_its_https_citations(self, client):
        from .companion import call_spark

        stream = client.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
        cite = {"type": "url_citation", "url": "https://alabado.org/home/", "title": "Museo Casa del Alabado", "start_index": 0, "end_index": 5}
        stream.iter_bytes.return_value = [json.dumps({"status": "completed", "output": [
            {"type": "reasoning", "encrypted_content": "x", "summary": []},
            {"type": "message", "phase": "commentary", "content": [{"type": "output_text", "text": "Busco el horario.", "annotations": []}]},
            {"type": "web_search_call", "status": "completed", "action": {"type": "search", "query": "q"}},
            {"type": "message", "content": [{"type": "output_text", "text": "Abre de 10:00 a 17:30.",
                                              "annotations": [cite, cite, {"type": "url_citation", "url": "javascript:alert(1)", "title": "x"}]}]},
        ]}).encode()]
        result = call_spark("rules", "{}", web_search=True, basis=synthetic.REAL)
        self.assertEqual(result["text"], "Abre de 10:00 a 17:30.")
        self.assertEqual(result["citations"], [{"url": "https://alabado.org/home/", "title": "Museo Casa del Alabado"}])
        self.assertEqual(result["web_searches"], 1)
        self.assertEqual(client.return_value.__enter__.return_value.stream.call_args.kwargs["json"]["tools"], [{"type": "web_search"}])

    @patch.dict(os.environ, {"MODEL_API_KEY": "synthetic-key"})
    @patch("assistance.companion.httpx.Client")
    def test_a_call_without_a_decided_basis_sends_nothing(self, client):
        from .companion import CompanionUnavailable, call_spark

        for basis in (None, True, False, "synthetic"):
            with self.assertRaisesMessage(CompanionUnavailable, "privacy_review_required"):
                call_spark("rules", "{}", basis=basis)
        with self.assertRaisesMessage(CompanionUnavailable, "privacy_review_required"):
            call_spark("rules", "{}")
        client.assert_not_called()
