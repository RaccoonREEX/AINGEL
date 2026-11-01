"""The Meta usage ledger (assistance.usage) bills every call to the account that made it, through the real endpoints:
the account comes from the authenticated request on the server (care.consent.meta_account_denial), never from the
client. Requests to Meta are intercepted at the HTTP client; the MetaUsage rows checked are the real ones."""

import json
import os
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from care.models import Profile
from care.testing import adult, authorize

from . import usage
from .meta_quota import bind_account
from .models import MetaUsage

# The server's own synthetic fixtures with Meta, as on a synthetic test server (no personal content).
SYNTHETIC = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_SYNTHETIC_TESTS_ONLY": "1",
             "AINGEL_REAL_DATA": "0", "AINGEL_VIDEO_CLIPS": "1"}
TOKENS = {"input_tokens": 1000, "output_tokens": 200, "output_tokens_details": {"reasoning_tokens": 50},
          "input_tokens_details": {"cached_tokens": 0}}
VIDEO_ANSWER = {"type": "function_call", "name": "report_changes",
                "arguments": '{"events":[{"kind":"moved","what":"un cuadrado","certainty":"observed"}],"say":"Un cuadrado se movió."}'}


class FakeMeta:
    """Stands in for httpx.Client in every module that calls Meta: answers post() and stream() with a completed
    response and its usage, like the Responses API."""

    def __init__(self, output=None, body=None):
        self.output = output or [{"type": "message", "content": [{"type": "output_text", "text": "Respuesta."}]}]
        self.body = body
        self.calls = 0

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def reply(self):
        self.calls += 1
        return self.body if self.body is not None else {"status": "completed", "usage": TOKENS, "output": self.output}

    def post(self, *args, **kwargs):
        return Reply(self.reply())

    def stream(self, *args, **kwargs):
        return Reply(self.reply())

    def delete(self, *args, **kwargs):
        return Reply({})


class Reply:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    def json(self):
        return self.data

    def iter_bytes(self):
        yield json.dumps(self.data).encode()


def account(username):
    user = adult(get_user_model().objects.create_user(username=username))
    profile = authorize(Profile.objects.create(owner=user, display_name="Ficticio"), {"meta_data": True})
    client = APIClient()
    client.force_authenticate(user)
    return user, profile, client


@patch.dict(os.environ, SYNTHETIC)
class LedgerAccountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.ana, self.ana_profile, self.ana_client = account("ledger-ana")
        self.beto, self.beto_profile, self.beto_client = account("ledger-beto")

    def tearDown(self):
        bind_account(None)

    def rows(self, feature):
        return list(MetaUsage.objects.filter(feature=feature).order_by("id").values_list("user_id", flat=True))

    def test_scene_is_billed_to_the_account_that_asked(self):
        with patch("assistance.scene.httpx.Client", FakeMeta()):
            for client in (self.ana_client, self.beto_client):
                response = client.post("/api/v1/scene/", {"locale": "es-EC", "fixture": "shapes"}, format="multipart")
                self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.rows("scene"), [self.ana.pk, self.beto.pk])
        row = MetaUsage.objects.filter(feature="scene").first()
        self.assertEqual((row.input_tokens, row.output_tokens), (1000, 200))
        self.assertGreater(row.cost_usd, 0)

    def test_locate_is_billed_to_the_account_that_asked(self):
        sam = FakeMeta(output=[{"type": "message", "content": [{"type": "output_text", "text": ""}]}])
        with patch("assistance.locate.httpx.Client", sam):
            response = self.beto_client.post("/api/v1/locate/", {"locale": "es-EC", "fixture": "blue_square"}, format="multipart")
        self.assertEqual(sam.calls, 1, response.data)
        self.assertEqual(self.rows("locate"), [self.beto.pk])

    def test_conversation_is_billed_to_the_account_that_asked(self):
        with patch("assistance.companion.httpx.Client", FakeMeta()):
            response = self.ana_client.post(f"/api/v1/profiles/{self.ana_profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.rows("companion"), [self.ana.pk])

    def test_video_is_billed_to_the_account_that_asked(self):
        with patch("assistance.video.httpx.Client", FakeMeta(output=[VIDEO_ANSWER])):
            response = self.beto_client.post("/api/v1/vision/clip/", {"locale": "es-EC", "session": "ledger-1", "seq": 1, "fixture": "moving_square"}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.rows("video"), [self.beto.pk])

    def test_a_client_supplied_account_id_is_ignored(self):
        with patch("assistance.scene.httpx.Client", FakeMeta()):
            response = self.ana_client.post("/api/v1/scene/", {"locale": "es-EC", "fixture": "shapes", "user": self.beto.pk, "user_id": self.beto.pk, "account": self.beto.pk}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.rows("scene"), [self.ana.pk])

    def test_daily_cap_counts_calls_from_every_feature(self):
        """Before, scene/companion/locate/video rows had no account, so the per-account cap never saw them."""
        with patch("assistance.scene.httpx.Client", FakeMeta()):
            for _ in range(2):
                self.assertEqual(self.ana_client.post("/api/v1/scene/", {"locale": "es-EC", "fixture": "shapes"}, format="multipart").status_code, 200)
        spent = sum(MetaUsage.objects.filter(user=self.ana).values_list("cost_usd", flat=True))
        with patch.dict(os.environ, {"AINGEL_META_USER_DAILY_USD": str(spent)}), patch("assistance.scene.httpx.Client", FakeMeta()) as meta:
            refused = self.ana_client.post("/api/v1/scene/", {"locale": "es-EC", "fixture": "shapes"}, format="multipart")
            self.assertEqual(refused.data["error"], "meta_account_budget_exhausted")
            self.assertEqual(meta.calls, 0)
            self.assertEqual(self.beto_client.post("/api/v1/scene/", {"locale": "es-EC", "fixture": "shapes"}, format="multipart").status_code, 200)


class BilledAccountTests(TestCase):
    def tearDown(self):
        bind_account(None)

    def test_explicit_user_then_bound_account_then_none(self):
        user = get_user_model().objects.create_user(username="ledger-explicit")
        other = get_user_model().objects.create_user(username="ledger-bound")
        self.assertIsNone(usage.billed_account())
        bind_account(other)
        self.assertEqual(usage.billed_account(), other.pk)
        self.assertEqual(usage.billed_account(user), user.pk)
        usage.record("scene", "muse-spark-1.3", "minimal", TOKENS)
        self.assertEqual(MetaUsage.objects.get().user_id, other.pk)
        self.assertEqual(MetaUsage.objects.get().cost_usd, Decimal("0.002100"))
