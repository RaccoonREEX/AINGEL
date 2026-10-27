import io
import os
from unittest.mock import patch

import httpx
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from PIL import Image
from rest_framework.test import APIClient

from .scene import SceneUnavailable, describe_scene, normalize_image


def fixture_image():
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(
        "fixture.png", buffer.getvalue(), content_type="image/png"
    )


class SceneContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="fixture-user")

    def test_anonymous_upload_denied(self):
        response = self.client.post(
            "/api/v1/scene/", {"image": fixture_image(), "locale": "en-US"}
        )
        self.assertEqual(response.status_code, 403)

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "mock"})
    def test_mock_is_explicit_and_claims_no_scene(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/scene/", {"image": fixture_image(), "locale": "es-EC"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["mode"], "mock")
        self.assertIn("no se analizó", response.data["text"])
        self.assertIsNone(response.data["model"])
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_invalid_image_rejected(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/scene/",
            {
                "image": SimpleUploadedFile("bad.png", b"not an image"),
                "locale": "en-US",
            },
        )
        self.assertEqual(response.data["error"], "image_invalid")

    def test_oversized_image_rejected(self):
        upload = SimpleUploadedFile("big.png", b"x" * (5 * 1024 * 1024 + 1))
        with self.assertRaisesRegex(ValueError, "image_too_large"):
            normalize_image(upload)

    def test_unsupported_locale_rejected(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            "/api/v1/scene/", {"image": fixture_image(), "locale": "xx"}
        )
        self.assertEqual(response.status_code, 400)


class MetaBoundaryTests(SimpleTestCase):
    @patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": ""})
    def test_missing_key_fails_closed(self):
        with self.assertRaisesRegex(SceneUnavailable, "meta_not_configured"):
            describe_scene(b"fixture", "en-US", True)

    @patch.dict(os.environ, {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-only"})
    def test_personal_content_gate(self):
        with self.assertRaisesRegex(SceneUnavailable, "privacy_review_required"):
            describe_scene(b"fixture", "en-US", False)

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "test-only",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.scene.httpx.Client")
    def test_fixed_meta_destination_and_response_parsing(self, client):
        client.return_value.__enter__.return_value.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
            json={
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "A blue square."}],
                    }
                ],
            },
        )
        result = describe_scene(b"synthetic", "en-US", True)
        call = client.return_value.__enter__.return_value.post.call_args
        self.assertEqual(call.args[0], "https://api.meta.ai/v1/responses")
        self.assertEqual(call.kwargs["json"]["model"], "muse-spark-1.3")
        self.assertEqual(call.kwargs["json"]["reasoning"], {"effort": "minimal"})
        instruction = call.kwargs["json"]["input"][0]["content"][0]["text"]
        self.assertIn("cannot establish whether a route is safe", instruction)
        self.assertIn("Never say that the path is safe", instruction)
        self.assertIn("no obstacles or dangers", instruction)
        self.assertFalse(call.kwargs["json"]["store"])
        self.assertEqual(result["text"], "A blue square.")

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "test-only",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.scene.httpx.Client")
    def test_incomplete_response_is_not_presented_as_success(self, client):
        client.return_value.__enter__.return_value.post.return_value = httpx.Response(
            200,
            request=httpx.Request("POST", "https://api.meta.ai/v1/responses"),
            json={"status": "incomplete", "output": []},
        )
        with self.assertRaisesRegex(SceneUnavailable, "^meta_incomplete$"):
            describe_scene(b"synthetic", "en-US", True)

    @patch.dict(
        os.environ,
        {
            "AINGEL_AI_MODE": "meta",
            "MODEL_API_KEY": "test-only",
            "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
        },
    )
    @patch("assistance.scene.httpx.Client")
    def test_provider_error_does_not_escape(self, client):
        client.return_value.__enter__.return_value.post.side_effect = (
            httpx.ConnectError("sensitive upstream body")
        )
        with self.assertRaisesRegex(SceneUnavailable, "^meta_unavailable$"):
            describe_scene(b"synthetic", "en-US", True)
