"""Regression (Astra, second audit): the temporal video context of a real, authorized session must never reach a
synthetic fixture payload, another account, another profile, or the same person after a revocation or session end.

Every request to Meta is intercepted at the HTTP client and its exact payload inspected; the model's reply is faked
so that each real clip leaves a private event («ZZQ-REAL-…») in the context.
"""

import base64
import json
import os
import threading
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from care.consent import decide
from care.models import Membership, Profile
from care.testing import adult, authorize

from . import synthetic

ENV = {
    "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_VIDEO_CLIPS": "1", "AINGEL_VIDEO_REAL": "1",
    "AINGEL_REAL_DATA": "1", "AINGEL_SYNTHETIC_TESTS_ONLY": "1", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0",
}
FIXTURE_URL = "data:video/mp4;base64," + base64.b64encode(synthetic.moving_square_clip()).decode("ascii")
REAL_CLIP = synthetic.moving_square_clip(seconds=5)  # differs from the fixture, so the fake model can tell them apart
SESSION = "shared-session-1"


class Wire:
    """httpx.Client stand-in: records each payload; a real clip gets a private event back, a fixture a fictitious one."""

    def __init__(self):
        self.sent, self.lock, self.count = [], threading.Lock(), 0

    def __call__(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None, data=None, files=None):
        video = json["input"][0]["content"][1]["video_url"]
        with self.lock:
            self.count += 1
            fixture = video == FIXTURE_URL
            self.sent.append({"fixture": fixture, "payload": json})
            what = "un cuadrado azul" if fixture else f"ZZQ-REAL-{self.count} persona en la cocina"
        return Reply({"kind": "entered", "what": what, "certainty": "observed"})

    def text(self, fixture=None):
        return [__import__("json").dumps(x["payload"], ensure_ascii=False) for x in self.sent if fixture is None or x["fixture"] == fixture]


class Reply:
    def __init__(self, event):
        self.event = event

    def raise_for_status(self):
        return None

    def json(self):
        arguments = json.dumps({"events": [self.event], "say": "Algo cambió."})
        return {"status": "completed", "output": [{"type": "function_call", "name": "report_changes", "arguments": arguments}]}


def context_of(payload):
    """The «Recent observations» the model was given, as sent."""
    text = payload["input"][0]["content"][0]["text"]
    return json.loads(text.split("Recent observations (data): ", 1)[1])


class Accounts:
    def person(self, name):
        user = adult(get_user_model().objects.create_user(username=name))
        profile = Profile.objects.create(owner=user, display_name=f"ZZQ-NAME-{name}", allergies="ZZQ-ALLERGY",
                                         support_notes="Apoyos indicados: ZZQ-DIAGNOSIS", communication={"addressing": "formal"})
        return user, authorize(profile, camera_local=True, meta_video=True)

    def api_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def real(self, user, profile, seq, session=SESSION):
        return self.api_for(user).post("/api/v1/vision/clip/", {
            "clip": SimpleUploadedFile("clip.mp4", REAL_CLIP, "video/mp4"), "profile": str(profile.pk), "locale": "es-EC",
            "session": session, "seq": str(seq)}, format="multipart")

    def fixture(self, user, seq, session=SESSION):
        return self.api_for(user).post("/api/v1/vision/clip/", {"fixture": "moving_square", "locale": "es-EC", "session": session,
                                                               "seq": str(seq)}, format="multipart")


class VideoContextIsolationTests(Accounts, TestCase):
    def setUp(self):
        cache.clear()
        self.wire = Wire()
        self.patches = [patch.dict(os.environ, ENV), patch("assistance.video.httpx.Client", self.wire)]
        for item in self.patches:
            item.start()
        self.user, self.profile = self.person("video-owner")

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_astra_scenario_fixture_after_a_real_event_in_the_same_session(self):
        self.assertEqual(self.real(self.user, self.profile, 5).status_code, 200)
        self.real(self.user, self.profile, 6)
        # The real session does keep its private event: this is the context that must not leak.
        self.assertEqual([e["what"] for e in context_of(self.wire.sent[-1]["payload"])], ["ZZQ-REAL-1 persona en la cocina"])
        # Same account, same session id, the next sequence number: the fixture must not be fed the real context.
        response = self.fixture(self.user, 7)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["stale"])
        payload = self.wire.sent[-1]["payload"]
        self.assertTrue(self.wire.sent[-1]["fixture"])
        self.assertEqual(context_of(payload), [])
        sent = json.dumps(payload, ensure_ascii=False)
        for marker in ("ZZQ-REAL", "ZZQ-NAME", "ZZQ-ALLERGY", "ZZQ-DIAGNOSIS"):
            self.assertNotIn(marker, sent)
        self.assertNotIn('"addressing": "formal"', payload["instructions"])
        self.assertIn(json.dumps(synthetic.FICTIONAL_PREFERENCES, ensure_ascii=True), payload["instructions"])

    def test_fixture_sequence_is_separate_from_the_real_one(self):
        self.real(self.user, self.profile, 5)
        response = self.fixture(self.user, 1)  # a lower number than the real session's: not dropped as stale
        self.assertFalse(response.data["stale"])
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])

    def test_fixture_events_never_enter_a_real_context_either(self):
        self.fixture(self.user, 1)
        self.real(self.user, self.profile, 1)
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])

    def test_contexts_are_separate_per_account_and_per_profile(self):
        self.real(self.user, self.profile, 1)
        other, other_profile = self.person("video-other")
        self.real(other, other_profile, 1)
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])
        # A caregiver of the same profile, same session id: their own context, not the owner's.
        helper = adult(get_user_model().objects.create_user(username="video-helper"))
        Membership.objects.create(profile=self.profile, user=helper, relationship="hija")
        self.real(helper, self.profile, 1)
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])
        # The owner's own next clip still has its context: isolation, not loss.
        self.real(self.user, self.profile, 2)
        self.assertEqual([e["what"] for e in context_of(self.wire.sent[-1]["payload"])], ["ZZQ-REAL-1 persona en la cocina"])

    def test_revocation_invalidates_the_context(self):
        self.real(self.user, self.profile, 1)
        self.assertIsNone(decide(self.profile, self.user, "meta_video", "revoke"))
        self.profile.refresh_from_db()
        self.assertEqual(self.real(self.user, self.profile, 2).data["error"], "privacy_review_required")
        self.assertIsNone(decide(self.profile, self.user, "meta_video", "grant"))
        self.real(self.user, self.profile, 3)
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])

    def test_a_revoked_context_is_deleted_and_ending_the_session_after_a_revocation_still_works(self):
        from .video import context_key

        self.real(self.user, self.profile, 1)
        key = context_key(self.user, self.profile, SESSION)
        self.assertIsNotNone(cache.get(key))
        decide(self.profile, self.user, "meta_video", "revoke")
        self.profile.refresh_from_db()
        response = self.api_for(self.user).post("/api/v1/vision/clip/end/", {"profile": str(self.profile.pk), "session": SESSION}, format="json")
        self.assertEqual(response.status_code, 204)
        self.assertIsNone(cache.get(key))  # the same key as before the revocation: really gone, not just unreachable
        self.real(self.user, self.profile, 1)
        decide(self.profile, self.user, "meta_video", "grant")
        self.profile.refresh_from_db()
        self.real(self.user, self.profile, 2)
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])

    def test_ending_the_session_discards_the_context(self):
        self.real(self.user, self.profile, 1)
        response = self.api_for(self.user).post("/api/v1/vision/clip/end/", {"profile": str(self.profile.pk), "session": SESSION}, format="json")
        self.assertEqual(response.status_code, 204)
        self.real(self.user, self.profile, 1)  # the sequence was discarded too: not stale
        self.assertEqual(context_of(self.wire.sent[-1]["payload"]), [])
        outsider = adult(get_user_model().objects.create_user(username="video-outsider"))
        response = self.api_for(outsider).post("/api/v1/vision/clip/end/", {"profile": str(self.profile.pk), "session": SESSION}, format="json")
        self.assertEqual(response.status_code, 404)


class ConcurrentVideoContextTests(Accounts, TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.wire = Wire()
        # The audit row is the only database write on this path; SQLite's shared test database locks on concurrent
        # writes, and the audit trail is not what this test is about.
        self.patches = [patch.dict(os.environ, ENV), patch("assistance.video.httpx.Client", self.wire), patch("assistance.video.audit")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()

    def test_concurrent_accounts_with_the_same_session_id(self):
        people = [self.person(f"video-concurrent-{i}") for i in range(4)]
        start, errors = threading.Barrier(len(people)), []

        def run(user, profile):
            try:
                start.wait()
                for seq in range(1, 4):
                    self.real(user, profile, seq)
                    self.fixture(user, seq + 10)
            except Exception as error:  # surfaced below
                errors.append(error)

        threads = [threading.Thread(target=run, args=person) for person in people]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        fixtures = [x["payload"] for x in self.wire.sent if x["fixture"]]
        self.assertTrue(fixtures)
        for payload in fixtures:
            self.assertEqual(context_of(payload), [])
            self.assertNotIn("ZZQ-", json.dumps(payload, ensure_ascii=False))
        # Each real payload holds at most that account's own earlier events: never more than its own two before it.
        for payload in (x["payload"] for x in self.wire.sent if not x["fixture"]):
            self.assertLessEqual(len(context_of(payload)), 2)
