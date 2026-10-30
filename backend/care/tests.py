from datetime import timedelta
import hashlib
import io
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from .models import Invitation, Membership, Memory, Message, Profile, Routine


class CareTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="primary")
        cls.family = get_user_model().objects.create_user(username="family")
        cls.outsider = get_user_model().objects.create_user(username="outsider")
        cls.profile = Profile.objects.create(
            owner=cls.owner, display_name="Synthetic user"
        )
        cls.base = f"/api/v1/profiles/{cls.profile.id}/"

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def invite(self, user=None, **kwargs):
        return self.client.post(
            self.base + "circle/",
            {
                "username": (user or self.family).username,
                "relationship": "Family",
                **kwargs,
            },
            format="json",
        )

    def join(self, **kwargs):
        invitation = self.invite(**kwargs)
        self.assertEqual(invitation.status_code, 201)
        self.client.force_authenticate(self.family)
        return self.client.post(
            "/api/v1/invites/accept/", {"code": invitation.data["code"]}, format="json"
        )

    def test_profile_is_draft_without_caregiver(self):
        response = self.client.get(self.base)
        self.assertFalse(response.data["ready"])
        self.assertEqual(response.data["caregiver_count"], 0)

    def test_invitation_does_not_grant_access_before_acceptance(self):
        self.invite()
        self.client.force_authenticate(self.family)
        self.assertEqual(self.client.get(self.base).status_code, 404)

    def test_invitation_requires_intended_account_and_is_single_use(self):
        invitation = self.invite()
        code = invitation.data["code"]
        self.assertFalse(Invitation.objects.filter(token_hash=code).exists())
        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.post("/api/v1/invites/accept/", {"code": code}).status_code, 404
        )
        self.client.force_authenticate(self.family)
        self.assertEqual(
            self.client.post("/api/v1/invites/accept/", {"code": code}).status_code, 201
        )
        self.assertEqual(
            self.client.post("/api/v1/invites/accept/", {"code": code}).status_code, 404
        )

    def test_pending_slots_limit_to_four(self):
        for i in range(4):
            user = get_user_model().objects.create_user(username=f"invitee{i}")
            self.assertEqual(self.invite(user).status_code, 201)
        self.assertEqual(self.invite().status_code, 400)
        self.assertEqual(Invitation.objects.count(), 4)

    def test_expired_invitation_releases_slot_and_cannot_be_accepted(self):
        invitation = self.invite()
        Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.client.force_authenticate(self.family)
        self.assertEqual(
            self.client.post(
                "/api/v1/invites/accept/", {"code": invitation.data["code"]}
            ).status_code,
            404,
        )
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.invite().status_code, 201)

    def test_owner_cannot_be_own_caregiver(self):
        self.assertEqual(self.invite(self.owner).status_code, 400)

    def test_joined_caregiver_can_configure_but_cannot_read_memory_by_default(self):
        self.assertEqual(self.join().status_code, 201)
        response = self.client.patch(
            self.base, {"allergies": "synthetic allergy note"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.base + "memories/").status_code, 403)
        self.assertEqual(
            self.client.post(
                self.base + "ask/", {"tool": "search_memory", "entity": "keys"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                self.base + "circle/",
                {"username": "outsider", "relationship": "Friend"},
            ).status_code,
            403,
        )

    def test_readonly_caregiver_cannot_configure_or_create_routine(self):
        self.join(can_configure=False)
        self.assertEqual(
            self.client.patch(
                self.base, {"display_name": "changed"}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.post(self.base + "routines/", {}).status_code, 403)

    def test_revocation_immediately_removes_access_and_restores_draft(self):
        self.join()
        member = Membership.objects.get(profile=self.profile)
        self.client.force_authenticate(self.owner)
        self.assertEqual(
            self.client.delete(self.base + f"circle/{member.id}/").status_code, 204
        )
        self.assertFalse(self.client.get(self.base).data["ready"])
        self.client.force_authenticate(self.family)
        for path in ["", "routines/", "messages/", "memories/"]:
            self.assertEqual(self.client.get(self.base + path).status_code, 404)

    def test_caregiver_can_leave_but_cannot_revoke_another_member(self):
        self.join()
        member = Membership.objects.get(user=self.family)
        another = Membership.objects.create(
            profile=self.profile, user=self.outsider, relationship="Friend"
        )
        self.assertEqual(
            self.client.delete(self.base + f"circle/{another.id}/").status_code, 403
        )
        self.assertEqual(
            self.client.delete(self.base + f"circle/{member.id}/").status_code, 204
        )

    def test_outsider_cannot_list_or_modify_profile(self):
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get("/api/v1/profiles/").data, [])
        self.assertEqual(
            self.client.patch(self.base, {"allergies": "tamper"}).status_code, 404
        )

    def test_preference_and_timezone_validation(self):
        self.assertEqual(
            self.client.patch(
                self.base, {"preferences": {"diagnosis": "fake"}}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                self.base, {"timezone": "invalid/zone"}, format="json"
            ).status_code,
            400,
        )

    def test_no_memory_never_invents_location(self):
        response = self.client.post(
            self.base + "ask/", {"tool": "search_memory", "entity": "keys"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answer_code"], "no_evidence")
        self.assertIsNone(response.data["evidence"])
        self.assertFalse(response.data["found"])

    def memory(self, location="Desk", observed=None):
        return Memory.objects.create(
            profile=self.profile,
            entity="keys",
            location=location,
            observed_at=observed or timezone.now(),
            recorded_by=self.owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

    def test_retrieval_latest_matching_fact_ignores_expired_and_other_profiles(self):
        self.memory("Old table", timezone.now() - timedelta(hours=2))
        latest = self.memory("Latest desk")
        other = Profile.objects.create(owner=self.outsider, display_name="Other")
        Memory.objects.create(
            profile=other,
            entity="keys",
            location="Other user's room",
            observed_at=timezone.now(),
            recorded_by=self.outsider,
            expires_at=timezone.now() + timedelta(days=7),
        )
        expired = self.memory("Expired place")
        expired.expires_at = timezone.now() - timedelta(seconds=1)
        expired.save()
        response = self.client.post(
            self.base + "ask/", {"tool": "search_memory", "entity": "KEYS"}
        )
        self.assertEqual(response.data["evidence"]["id"], str(latest.id))
        self.assertEqual(response.data["evidence"]["source"], "user_report")

    def test_memory_requires_confirmation_and_rejects_future(self):
        data = {
            "entity": "keys",
            "location": "Desk",
            "observed_at": timezone.now().isoformat(),
        }
        self.assertEqual(
            self.client.post(self.base + "memories/", data).status_code, 400
        )
        data["confirmed"] = "true"
        data["observed_at"] = (timezone.now() + timedelta(days=1)).isoformat()
        self.assertEqual(
            self.client.post(self.base + "memories/", data).status_code, 400
        )

    def test_memory_read_permission_does_not_grant_write(self):
        self.join(can_view_memories=True)
        self.assertEqual(self.client.get(self.base + "memories/").status_code, 200)
        self.assertEqual(self.client.post(self.base + "memories/", {}).status_code, 403)

    def test_private_evidence_access_and_deletion(self):
        with tempfile.TemporaryDirectory() as root, override_settings(
            PRIVATE_MEDIA_ROOT=Path(root)
        ):
            image = io.BytesIO()
            Image.new("RGB", (32, 32), "blue").save(image, format="PNG")
            response = self.client.post(
                self.base + "memories/",
                {
                    "entity": "keys",
                    "location": "Desk",
                    "observed_at": timezone.now().isoformat(),
                    "confirmed": "true",
                    "evidence": SimpleUploadedFile(
                        "fixture.png", image.getvalue(), "image/png"
                    ),
                },
            )
            self.assertEqual(response.status_code, 201)
            url = self.base + f"memories/{response.data['id']}/"
            self.assertEqual(len(list(Path(root).iterdir())), 1)
            self.client.force_authenticate(self.outsider)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_authenticate(self.owner)
            image_response = self.client.get(url)
            self.assertEqual(image_response.status_code, 200)
            self.assertEqual(image_response["Cache-Control"], "no-store")
            image_response.close()
            self.assertEqual(self.client.delete(url).status_code, 204)
            self.assertEqual(list(Path(root).iterdir()), [])
            self.assertFalse(
                self.client.post(
                    self.base + "ask/", {"tool": "search_memory", "entity": "keys"}
                ).data["found"]
            )

    def test_routine_shows_who_organizes_it(self):
        self.owner.first_name = "Lucía"
        self.owner.save(update_fields=["first_name"])
        data = {"category": "water", "title": "Water", "at": "11:00", "weekdays": [0, 1, 2, 3, 4, 5, 6]}
        created = self.client.post(self.base + "routines/", data, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["author_name"], "Lucía")
        self.owner.first_name = ""
        self.owner.save(update_fields=["first_name"])
        listed = self.client.get(self.base + "routines/").data
        rows = listed["items"] if isinstance(listed, dict) else listed
        self.assertEqual(rows[0]["author_name"], "primary")

    def test_routine_weekdays_and_time_are_validated(self):
        data = {"category": "sleep", "title": "Sleep", "at": "22:00", "weekdays": []}
        self.assertEqual(
            self.client.post(self.base + "routines/", data, format="json").status_code,
            400,
        )
        data["weekdays"] = [7]
        self.assertEqual(
            self.client.post(self.base + "routines/", data, format="json").status_code,
            400,
        )
        data["weekdays"] = [0]
        data["at"] = "99:99"
        self.assertEqual(
            self.client.post(self.base + "routines/", data, format="json").status_code,
            400,
        )

    def test_medication_schedule_does_not_imply_completion(self):
        response = self.client.post(
            self.base + "routines/",
            {
                "category": "medicine",
                "title": "Synthetic reminder",
                "at": "08:00",
                "weekdays": list(range(7)),
                "instructions": "User-supplied instructions only",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["confirmed_today"])
        url = self.base + f"routines/{response.data['id']}/confirm/"
        response = self.client.post(url)
        self.assertTrue(response.data["confirmed_today"])
        self.assertEqual(response.data["confirmation_actor"], "primary")
        self.assertFalse(self.client.delete(url).data["confirmed_today"])

    def test_care_messages_preserve_author_and_original_text(self):
        self.join()
        message = self.client.post(
            self.base + "messages/", {"body": "Llegaré a las cinco.", "locale": "es-EC"}
        )
        self.assertEqual(message.status_code, 201)
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.base + "ask/", {"tool": "get_care_messages"})
        self.assertEqual(response.data["items"][0]["author"], "family")
        self.assertEqual(response.data["items"][0]["body"], "Llegaré a las cinco.")

    def test_profile_and_memory_access_are_audited_without_sensitive_text(self):
        self.client.patch(
            self.base, {"allergies": "secret synthetic allergy"}, format="json"
        )
        self.client.get(self.base + "memories/")
        response = self.client.get(self.base + "audit/")
        self.assertIn("profile.updated", str(response.data))
        self.assertNotIn("secret synthetic allergy", str(response.data))
        self.join()
        self.assertEqual(self.client.get(self.base + "audit/").status_code, 403)


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(
            username="primary", password="Test-only!Strong-4829"
        )

    def test_login_requires_csrf_even_before_authentication(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "primary", "password": "Test-only!Strong-4829"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_session_login_logout_and_csrf_rotation(self):
        token = self.client.get("/api/v1/auth/session/").json()["csrf"]
        login = self.client.post(
            "/api/v1/auth/login/",
            {"username": "primary", "password": "Test-only!Strong-4829"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(login.status_code, 200)
        self.assertNotEqual(token, login.json()["csrf"])
        self.assertEqual(
            self.client.get("/api/v1/auth/session/").json()["user"]["username"],
            "primary",
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=login.json()["csrf"]
            ).status_code,
            200,
        )
        self.assertIsNone(self.client.get("/api/v1/auth/session/").json()["user"])

    def test_registration_rejects_weak_password_and_accepts_strong(self):
        token = self.client.get("/api/v1/auth/session/").json()["csrf"]
        weak = self.client.post(
            "/api/v1/auth/register/",
            {"username": "new-user", "password": "123"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(weak.status_code, 400)
        valid = self.client.post(
            "/api/v1/auth/register/",
            {"username": "new-user", "password": "Synthetic!Long-19483"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(valid.status_code, 200)

    def test_sensitive_api_responses_not_cached(self):
        self.assertEqual(
            self.client.get("/api/v1/auth/session/")["Cache-Control"], "no-store"
        )
