import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .consent import TERMS_VERSION, meta_allowed
from .models import ConsentGrant, Membership, Profile, SubjectInvite
from .testing import adult, authorize

META = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "synthetic-key", "AINGEL_REAL_DATA": "1"}
ASK = {"turns": [{"role": "user", "text": "¿Qué es la presión arterial?"}]}


def fake_answer(*args, **kwargs):
    return {"mode": "meta", "model": "muse-spark-1.3", "text": "Respuesta.", "latency_ms": 1}


class AgeAndConsentTests(TestCase):
    """Adults only (Meta Model API terms); the person a profile describes decides, from their own account."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.caregiver = adult(users.create_user(username="carer"))
        self.person = adult(users.create_user(username="person"))
        self.relative = adult(users.create_user(username="relative"))
        self.outsider = adult(users.create_user(username="outsider"))
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user)
        return self.client

    def create_for_other(self, **extra):
        return self.as_user(self.caregiver).post("/api/v1/profiles/", {"display_name": "Rosa", "subject_adult": True, **extra}, format="json")

    def ask(self, user, profile):
        with patch.dict(os.environ, {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}), \
                patch("assistance.conversation.call_spark", side_effect=fake_answer), \
                patch("assistance.conversation.best_topic", return_value=None):
            return self.as_user(user).post(f"/api/v1/profiles/{profile}/conversation/", ASK, format="json")

    def link(self, profile_id):
        code = self.as_user(self.caregiver).post(f"/api/v1/profiles/{profile_id}/consent/invite/").data["code"]
        return self.as_user(self.person).post("/api/v1/consent/redeem/", {"code": code}, format="json")

    def test_accounts_without_the_adult_declaration_cannot_use_meta_until_they_declare(self):
        legacy = get_user_model().objects.create_user(username="legacy", password="Synthetic!Long-19483")
        profile = authorize(Profile.objects.create(owner=legacy, display_name="Legacy"), {"meta_data": True})
        legacy.aingel_policy.delete()  # created before the age policy
        self.assertEqual(self.ask(legacy, profile.pk).data, {"error": "adult_declaration_required"})
        # Not even a server synthetic fixture skips it.
        with patch.dict(os.environ, {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}):
            synthetic = self.as_user(legacy).post(f"/api/v1/profiles/{profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
        self.assertEqual(synthetic.data, {"error": "adult_declaration_required"})
        client = APIClient(enforce_csrf_checks=False)
        client.force_login(legacy)
        self.assertEqual(client.post("/api/v1/auth/adult/", {"adult": True}, format="json").status_code, 400)
        declared = client.post("/api/v1/auth/adult/", {"adult": True, "terms_version": TERMS_VERSION}, format="json")
        self.assertTrue(declared.json()["user"]["adult_declared"])
        # An account from before the territory policy also declares where it is (care.territory).
        self.assertEqual(self.ask(legacy, profile.pk).data, {"error": "territory_declaration_required"})
        located = client.post("/api/v1/auth/territory/", {"territory": "outside_restricted", "territory_version": "2026-10-12"}, format="json")
        self.assertEqual(located.json()["user"]["territory"], "outside_restricted")
        self.assertEqual(self.ask(legacy, profile.pk).status_code, 200)

    def test_profiles_for_minors_are_not_supported_and_a_caregiver_cannot_accept_for_another_adult(self):
        self.assertEqual(self.create_for_other(subject_adult=False).data, {"subject_adult": ["subject_minor_not_supported"]})
        self.assertEqual(self.create_for_other(grants=["meta_conversation"]).data, {"grants": ["consent_subject_only"]})
        created = self.create_for_other()
        self.assertEqual((created.status_code, created.data["subject_status"]), (201, "pending_consent"))
        profile = Profile.objects.get(pk=created.data["id"])
        refused = self.as_user(self.caregiver).post(f"/api/v1/profiles/{profile.pk}/consent/", {"purpose": "meta_conversation", "decision": "grant"}, format="json")
        self.assertEqual((refused.status_code, refused.data), (403, {"error": "consent_subject_only"}))
        with patch.dict(os.environ, META):
            self.assertFalse(meta_allowed(profile, "conversation"))
        self.assertEqual(self.ask(self.caregiver, profile.pk).data, {"error": "privacy_review_required"})

    def test_the_person_accepts_with_a_one_time_code_from_their_own_account(self):
        profile_id = self.create_for_other().data["id"]
        Membership.objects.create(profile_id=profile_id, user=self.relative, relationship="Hija")
        code = self.as_user(self.caregiver).post(f"/api/v1/profiles/{profile_id}/consent/invite/").data["code"]
        # Whoever set it up, or anyone in the circle, cannot accept as if they were the person.
        for user in (self.caregiver, self.relative):
            refused = self.as_user(user).post("/api/v1/consent/redeem/", {"code": code}, format="json")
            self.assertEqual((refused.status_code, refused.data), (403, {"error": "consent_subject_only"}))
        linked = self.as_user(self.person).post("/api/v1/consent/redeem/", {"code": code}, format="json")
        self.assertEqual((linked.status_code, linked.data["subject_status"], linked.data["is_subject"]), (200, "subject_linked", True))
        # Single use.
        self.assertEqual(self.as_user(self.outsider).post("/api/v1/consent/redeem/", {"code": code}, format="json").data, {"error": "consent_code_invalid"})
        self.assertEqual(self.ask(self.caregiver, profile_id).data, {"error": "privacy_review_required"})
        decided = self.as_user(self.person).post(f"/api/v1/profiles/{profile_id}/consent/", {"purpose": "meta_conversation", "decision": "grant"}, format="json")
        self.assertEqual(decided.status_code, 200)
        self.assertEqual(ConsentGrant.objects.get(profile_id=profile_id).decided_by, self.person)
        self.assertEqual(self.ask(self.caregiver, profile_id).status_code, 200)
        # The person reads their profile; the circle's administration stays with the owner.
        self.assertEqual(self.as_user(self.person).get(f"/api/v1/profiles/{profile_id}/").data["role"], "subject")

    def test_codes_expire_and_need_an_adult_account(self):
        profile_id = self.create_for_other().data["id"]
        code = self.as_user(self.caregiver).post(f"/api/v1/profiles/{profile_id}/consent/invite/").data["code"]
        undeclared = get_user_model().objects.create_user(username="undeclared")
        self.assertEqual(self.as_user(undeclared).post("/api/v1/consent/redeem/", {"code": code}, format="json").data,
                         {"error": "adult_declaration_required"})
        SubjectInvite.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(self.as_user(self.person).post("/api/v1/consent/redeem/", {"code": code}, format="json").data,
                         {"error": "consent_code_invalid"})

    def test_a_general_authorization_never_stands_in_for_a_specific_one(self):
        profile = authorize(Profile.objects.create(owner=self.person, display_name="Self"), meta_conversation=True, camera_local=True)
        with patch.dict(os.environ, META):
            self.assertTrue(meta_allowed(profile, "conversation"))
            self.assertFalse(meta_allowed(profile, "personalization"))
            self.assertFalse(meta_allowed(profile, "image"))  # camera + conversation are not «photos to Meta»
            self.assertFalse(meta_allowed(profile, "video"))
            self.assertFalse(meta_allowed(profile, "audio"))

    def test_legal_review_blocks_every_decision_and_transfer(self):
        profile = authorize(Profile.objects.create(owner=self.person, display_name="Self"), {"meta_data": True, "camera": True})
        reviewed = self.as_user(self.person).post(f"/api/v1/profiles/{profile.pk}/consent/legal-review/")
        self.assertEqual(reviewed.data["subject_status"], "requires_legal_review")
        refused = self.as_user(self.person).post(f"/api/v1/profiles/{profile.pk}/consent/", {"purpose": "meta_photos", "decision": "grant"}, format="json")
        self.assertEqual(refused.data, {"error": "legal_review_required"})
        profile.refresh_from_db()
        with patch.dict(os.environ, META):
            self.assertFalse(meta_allowed(profile, "conversation"))

    def test_revoking_while_meta_answers_drops_the_answer(self):
        profile = authorize(Profile.objects.create(owner=self.person, display_name="Self"), {"meta_data": True})

        def revoked_meanwhile(*args, **kwargs):
            from .consent import decide
            decide(profile, self.person, "meta_conversation", "revoke")
            return fake_answer()

        with patch.dict(os.environ, {**META, "AINGEL_SYNTHETIC_TESTS_ONLY": "0"}), \
                patch("assistance.conversation.call_spark", side_effect=revoked_meanwhile), \
                patch("assistance.conversation.best_topic", return_value=None):
            response = self.as_user(self.person).post(f"/api/v1/profiles/{profile.pk}/conversation/", ASK, format="json")
        self.assertEqual((response.status_code, response.data), (409, {"error": "consent_changed"}))
        self.assertEqual(self.ask(self.person, profile.pk).data, {"error": "privacy_review_required"})

    def test_profiles_are_isolated(self):
        profile = authorize(Profile.objects.create(owner=self.person, display_name="Self"), {"meta_data": True})
        self.assertEqual(self.as_user(self.outsider).get(f"/api/v1/profiles/{profile.pk}/consent/").status_code, 404)
        self.assertEqual(self.as_user(self.outsider).post(f"/api/v1/profiles/{profile.pk}/consent/invite/").status_code, 404)
        self.assertEqual(self.ask(self.outsider, profile.pk).status_code, 404)

    def test_signing_up_for_oneself_records_the_persons_own_grants(self):
        created = self.as_user(self.person).post("/api/v1/profiles/", {"display_name": "Yo", "for_self": True,
                                                                       "grants": ["camera_local", "meta_photos"]}, format="json")
        self.assertEqual((created.status_code, created.data["subject_status"]), (201, "self"))
        grants = ConsentGrant.objects.filter(profile_id=created.data["id"])
        self.assertEqual({(g.purpose, g.status, g.decided_by_id, g.method) for g in grants},
                         {("camera_local", "granted", self.person.pk, "own_account_signup"), ("meta_photos", "granted", self.person.pk, "own_account_signup")})
        state = self.as_user(self.person).get(f"/api/v1/profiles/{created.data['id']}/consent/?locale=en-US").data
        self.assertTrue(state["is_subject"])
        # Meta Model API terms (docs/META_MODEL_API_TERMS.md): Standard models only, not used for training.
        self.assertIn("«Standard»", state["credits_notice"])
        self.assertIn("does not use it to train", state["credits_notice"])

    def test_purpose_texts_are_served_for_sign_up(self):
        data = self.as_user(self.person).get("/api/v1/consent/purposes/?locale=es-EC").data
        self.assertEqual([p["id"] for p in data["purposes"]][:3], ["camera_local", "microphone_local", "meta_conversation"])
        self.assertEqual(data["terms_version"], TERMS_VERSION)
        self.assertTrue(all(p["title"] and p["detail"] for p in data["purposes"]))


class SubjectConfirmationTests(TestCase):
    """Profiles from before the policy: whose data they hold is confirmed explicitly by the owner, never inferred."""

    def setUp(self):
        cache.clear()
        users = get_user_model().objects
        self.owner = adult(users.create_user(username="legacy-owner"))
        self.carer = adult(users.create_user(username="legacy-carer"))
        self.profile = Profile.objects.create(owner=self.owner, display_name="Legacy")  # default: pending_confirmation
        Membership.objects.create(profile=self.profile, user=self.carer, relationship="Hija")
        self.client = APIClient()

    def post(self, user, url, body=None):
        self.client.force_authenticate(user)
        return self.client.post(f"/api/v1/profiles/{self.profile.pk}/consent/{url}", body or {}, format="json")

    def test_nothing_is_enabled_until_the_owner_confirms(self):
        self.assertEqual(self.profile.subject_status, "pending_confirmation")
        self.assertEqual(self.post(self.owner, "", {"purpose": "meta_conversation", "decision": "grant"}).data,
                         {"error": "subject_confirmation_required"})
        with patch.dict(os.environ, META):
            self.assertFalse(meta_allowed(self.profile, "conversation"))
        self.client.force_authenticate(self.owner)
        self.assertTrue(self.client.get(f"/api/v1/profiles/{self.profile.pk}/consent/").data["can_confirm"])
        self.client.force_authenticate(self.carer)
        self.assertFalse(self.client.get(f"/api/v1/profiles/{self.profile.pk}/consent/").data["can_confirm"])

    def test_only_the_owner_confirms_and_only_once(self):
        self.assertEqual(self.post(self.carer, "confirm-subject/", {"for_self": True}).status_code, 403)
        self.assertEqual(self.post(self.owner, "confirm-subject/", {"for_self": "yes"}).data, {"error": "consent_request_invalid"})
        confirmed = self.post(self.owner, "confirm-subject/", {"for_self": True})
        self.assertEqual((confirmed.status_code, confirmed.data["subject_status"], confirmed.data["is_subject"]), (200, "self", True))
        self.assertEqual(self.post(self.owner, "confirm-subject/", {"for_self": False, "subject_adult": True}).data,
                         {"error": "subject_already_confirmed"})
        self.assertEqual(self.post(self.owner, "", {"purpose": "meta_conversation", "decision": "grant"}).status_code, 200)

    def test_set_up_for_another_adult_waits_for_that_person(self):
        self.assertEqual(self.post(self.owner, "confirm-subject/", {"for_self": False}).data, {"error": "subject_minor_not_supported"})
        confirmed = self.post(self.owner, "confirm-subject/", {"for_self": False, "subject_adult": True})
        self.assertEqual(confirmed.data["subject_status"], "pending_consent")
        self.assertEqual(self.post(self.owner, "invite/").status_code, 201)
