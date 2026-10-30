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
        self.owner = users.create_user(username="companion-owner")
        self.reader = users.create_user(username="companion-reader")
        self.outsider = users.create_user(username="companion-outsider")
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

    def test_authentication_scope_and_mock_mode_are_explicit(self):
        self.assertEqual(
            APIClient()
            .post(self.path, {"text": "Synthetic", "synthetic": True}, format="json")
            .status_code,
            403,
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.post(text="Synthetic", synthetic=True).status_code, 404)
        self.client.force_authenticate(self.reader)
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}):
            response = self.post(text="Synthetic question", synthetic=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "mock")
        self.assertIsNone(response.data["model"])
        self.assertIsNone(response.data["source"])
        self.assertIn("no se generó", response.data["text"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_explicit_synthetic_assertion_and_bounded_single_request(self):
        meta = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}
        with patch.dict(os.environ, meta), patch("assistance.companion.httpx.Client") as provider:
            # Meta mode without sign-up authorization: a real question needs the synthetic declaration.
            for value in ({"text": "Synthetic"}, {"text": "Synthetic", "synthetic": False}, {"text": "Synthetic", "synthetic": 1}):
                cache.clear()
                self.assertEqual(self.client.post(self.path, value, format="json").status_code, 400)
            provider.assert_not_called()
        invalid = [
            {"text": " ", "synthetic": True},
            {"text": "x" * 1001, "synthetic": True},
            {"text": ["synthetic"], "synthetic": True},
            {"text": "Synthetic", "synthetic": True, "history": ["PRIVATE"]},
        ]
        with patch("assistance.companion.httpx.Client") as provider:
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
        response = self.post(text="Synthetic", synthetic=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "privacy_review_required")
        provider.assert_not_called()

    def test_source_must_be_selected_exactly_and_cannot_be_invented(self):
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"}):
            self.assertEqual(
                self.post(
                    text="Synthetic", synthetic=True, topic_title="Only title"
                ).status_code,
                400,
            )
            with patch("assistance.companion.exact_topic", return_value=None) as lookup:
                response = self.post(
                    text="Synthetic",
                    synthetic=True,
                    topic_title="Unlisted topic",
                    topic_lang="es",
                )
                self.assertEqual(response.status_code, 404)
                lookup.assert_called_once_with("Unlisted topic", "es")
            with patch("assistance.companion.exact_topic", return_value=TOPIC):
                response = self.post(
                    text="Synthetic",
                    synthetic=True,
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
                    synthetic=True,
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
                        synthetic=True,
                        topic_title=TOPIC["title"],
                        topic_lang="es",
                    )
                    self.assertEqual(response.data["source"]["title"], TOPIC["title"])
                    response = self.post(
                        text="Synthetic",
                        synthetic=True,
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
                        synthetic=True,
                        topic_title=TOPIC["title"],
                        topic_lang="es",
                    )
                    self.assertEqual(response.status_code, 404)

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"})
    def test_per_user_chat_rate_is_bounded(self):
        for _ in range(6):
            self.assertEqual(
                self.post(text="Synthetic", synthetic=True).status_code, 200
            )
        self.assertEqual(self.post(text="Synthetic", synthetic=True).status_code, 429)

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
    def test_meta_payload_uses_only_allowed_settings_and_one_selected_public_source(
        self, _lookup, client
    ):
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
            synthetic=True,
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
        for marker in [
            "PRIVATE_PROFILE_MARKER",
            "PRIVATE_ALLERGY_MARKER",
            "PRIVATE_NOTES_MARKER",
            "PRIVATE_NAME_MARKER",
            "PRIVATE_COMMUNICATION_MARKER",
        ]:
            self.assertNotIn(marker, json.dumps(payload))
        event = AuditEvent.objects.get(action="companion.synthetic_chat")
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
    def test_provider_failure_is_sanitized(self, client):
        client.return_value.__enter__.return_value.stream.side_effect = (
            httpx.ConnectError("PRIVATE_PROVIDER_RESPONSE")
        )
        response = self.post(text="Synthetic", synthetic=True)
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
            response = self.post(text="Synthetic", synthetic=True)
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
        result = call_spark("rules", "{}", web_search=True)
        self.assertEqual(result["text"], "Abre de 10:00 a 17:30.")
        self.assertEqual(result["citations"], [{"url": "https://alabado.org/home/", "title": "Museo Casa del Alabado"}])
        self.assertEqual(result["web_searches"], 1)
        self.assertEqual(client.return_value.__enter__.return_value.stream.call_args.kwargs["json"]["tools"], [{"type": "web_search"}])
