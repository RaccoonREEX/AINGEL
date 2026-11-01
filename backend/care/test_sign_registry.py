"""AINGEL 3.0 phase 5 (test H): the sign registry, its validation rule and the corrections channel."""

import copy
import json
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from . import sign_registry
from .models import SignFeedback

PRINT_A, PRINT_B = "a" * 64, "b" * 64
FINGERPRINTS = Path(__file__).resolve().parents[2] / "web" / "src" / "components" / "aingel" / "signFingerprints.json"


def review(role="deaf_signer", decision="approve", day="2026-11-01", fingerprint=PRINT_A, region="Sierra (Quito)"):
    return {"reviewer": "Revisora ficticia", "role": role, "region": region, "decision": decision, "date": day,
            "fingerprint": fingerprint, "notes": None}


class StatusTests(TestCase):
    def test_nothing_is_validated_today(self):
        registry = sign_registry.public()
        self.assertEqual(registry["language"], "lsec")
        self.assertEqual(registry["summary"]["validated"], 0)
        self.assertEqual(registry["grammar_rules"], [])
        self.assertTrue(all(sign["status"] == "pending" and sign["fingerprint"] is None for sign in registry["signs"].values()))
        self.assertEqual(sign_registry.validated_ids(), set())

    def test_registry_matches_the_animations(self):
        prints = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
        self.assertEqual(set(prints), set(sign_registry.load()["signs"]))
        kinds = {sign["kind"] for sign in sign_registry.load()["signs"].values()}
        self.assertEqual(kinds, {"word", "letter", "number"})
        self.assertEqual(sign_registry.load()["signs"]["ñ"]["kind"], "letter")
        self.assertEqual(sign_registry.load()["signs"]["n3"]["kind"], "number")

    def test_validation_needs_two_approvals_one_by_a_deaf_signer(self):
        status = lambda *reviews: sign_registry.status({"reviews": list(reviews)})
        self.assertEqual(status()[0], "pending")
        self.assertEqual(status(review())[0], "in_review")
        self.assertEqual(status(review(role="interpreter"), review(role="linguist"))[0], "in_review")
        self.assertEqual(status(review(), review(role="interpreter", region="Costa (Guayaquil)")),
                         ("validated", PRINT_A, ["Costa (Guayaquil)", "Sierra (Quito)"]))

    def test_a_changed_animation_is_pending_review_again(self):
        approved = [review(), review(role="interpreter")]
        self.assertEqual(sign_registry.status({"reviews": approved})[0], "validated")
        # A newer animation was reviewed once: the earlier validation does not carry over.
        self.assertEqual(sign_registry.status({"reviews": approved + [review(day="2026-12-01", fingerprint=PRINT_B)]})[0], "in_review")

    def test_a_later_objection_blocks_validation(self):
        reviews = [review(), review(role="interpreter"), review(role="deaf_signer", decision="changes_requested", day="2026-11-02")]
        self.assertEqual(sign_registry.status({"reviews": reviews})[0], "changes_requested")
        reviews.append(review(decision="reject", day="2026-11-03"))
        self.assertEqual(sign_registry.status({"reviews": reviews})[0], "rejected")

    def test_invalid_registries_are_refused(self):
        good = sign_registry.load()
        for change in (
            lambda d: d.update(language="asl"),  # never another language passed off as LSEC
            lambda d: d["grammar_rules"].append({"id": "orden", "description": "Objeto antes del verbo"}),  # no source
            lambda d: d["signs"]["hola"].update(source=""),
            lambda d: d["signs"]["hola"]["reviews"].append({**review(), "role": "friend"}),
            lambda d: d["signs"]["hola"]["reviews"].append({**review(), "fingerprint": "abc"}),
        ):
            data = copy.deepcopy(good)
            change(data)
            with self.assertRaises(sign_registry.InvalidRegistry):
                sign_registry.validate(data)


class CommandTests(TestCase):
    def test_record_review_then_validate(self):
        original = sign_registry.REGISTRY.read_text(encoding="utf-8")
        prints = json.loads(FINGERPRINTS.read_text(encoding="utf-8"))
        try:
            out = StringIO()
            call_command("record_sign_review", "hola", reviewer="Revisora ficticia", role="deaf_signer", region="Sierra (Quito)",
                         decision="approve", stdout=out)
            self.assertIn("in_review", out.getvalue())
            call_command("record_sign_review", "hola", reviewer="Intérprete ficticio", role="interpreter", region="Sierra (Quito)",
                         decision="approve", stdout=out)
            self.assertIn("validated", out.getvalue())
            sign_registry.load.cache_clear()
            entry = sign_registry.public()["signs"]["hola"]
            self.assertEqual((entry["status"], entry["fingerprint"]), ("validated", prints["hola"]))
            self.assertEqual(sign_registry.validated_ids(), {"hola"})
        finally:
            sign_registry.REGISTRY.write_text(original, encoding="utf-8")
            sign_registry.load.cache_clear()

    def test_sync_adds_nothing_twice_and_never_validates(self):
        original = sign_registry.REGISTRY.read_text(encoding="utf-8")
        try:
            out = StringIO()
            call_command("sync_sign_registry", stdout=out)
            self.assertIn("(0 added)", out.getvalue())
            self.assertEqual(sign_registry.REGISTRY.read_text(encoding="utf-8"), original)
        finally:
            sign_registry.REGISTRY.write_text(original, encoding="utf-8")
            sign_registry.load.cache_clear()


class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="signs-reviewer")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_registry_endpoint(self):
        response = self.client.get("/api/v1/signs/registry/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["summary"], {"total": 81, "validated": 0})
        self.assertEqual(response.data["signs"]["agua"]["status"], "pending")
        self.assertNotIn("reviewer", json.dumps(response.data))  # names stay in the reviewed data file
        self.assertEqual(APIClient().get("/api/v1/signs/registry/").status_code, 403)

    def test_feedback_is_kept_for_reviewers_and_changes_nothing(self):
        response = self.client.post("/api/v1/signs/feedback/", {
            "sign": "agua", "verdict": "incorrect", "role": "deaf_signer", "region": "Costa", "comment": "La mano va más alto.",
            "fingerprint": PRINT_A,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        row = SignFeedback.objects.get()
        self.assertEqual((row.sign, row.verdict, row.role, row.user), ("agua", "incorrect", "deaf_signer", self.user))
        self.assertEqual(sign_registry.public()["signs"]["agua"]["status"], "pending")
        out = StringIO()
        call_command("export_sign_feedback", stdout=out)
        exported = json.loads(out.getvalue())
        self.assertEqual(exported["comment"], "La mano va más alto.")
        self.assertNotIn("user", exported)
        for bad in ({"sign": "inventada", "verdict": "correct", "role": "other"}, {"sign": "agua", "verdict": "perfecto", "role": "other"}):
            self.assertEqual(self.client.post("/api/v1/signs/feedback/", bad, format="json").status_code, 400)
