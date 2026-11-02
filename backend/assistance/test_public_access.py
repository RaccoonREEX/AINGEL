"""Mandatory tests for public access (AINGEL 3.0 final correction): brand-new accounts through the real endpoints,
in the consent-based production configuration, with no list of account IDs. Requests that would reach Meta are
intercepted at the HTTP client or the call function."""

import io
import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from care import territory
from care.consent import TERMS_VERSION

from . import synthetic
from .meta_quota import bind_account
from .models import MetaUsage
from .test_vision import Provider

# Production with consent, the target configuration: no AINGEL_META_ALLOWED_USER_IDS anywhere.
PUBLIC = {
    "AINGEL_ENV": "production", "AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1",
    "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0",
}
ANSWER = {"mode": "meta", "model": "muse-spark-1.3", "text": "Respuesta de prueba."}


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (90, 140, 200)).save(buffer, "PNG")
    return SimpleUploadedFile("foto.png", buffer.getvalue(), "image/png")


class Person:
    """A brand-new account going through sign-up, its own profile and its own decisions, as a client does."""

    def __init__(self, username, adult=True, located=territory.OUTSIDE):
        self.client = APIClient()
        body = {"username": username, "password": "Una-clave-de-prueba-larga-2026"}
        if adult:
            body |= {"adult": True, "terms_version": TERMS_VERSION}
        if located:
            body |= {"territory": located, "territory_version": territory.POLICY_VERSION}
        self.signup = self.client.post("/api/v1/auth/register/", body, format="json")

    def own_profile(self):
        response = self.client.post("/api/v1/profiles/", {"display_name": "Mi perfil", "locale": "es-EC", "for_self": True}, format="json")
        assert response.status_code == 201, response.data
        self.profile = response.data["id"]
        return self

    def decide(self, purpose, decision):
        response = self.client.post(f"/api/v1/profiles/{self.profile}/consent/", {"purpose": purpose, "decision": decision}, format="json")
        assert response.status_code == 200, response.data
        return self

    def converse(self, text="¿Qué puedo cocinar con arroz?"):
        return self.client.post(f"/api/v1/profiles/{self.profile}/conversation/", {"turns": [{"role": "user", "text": text}]}, format="json")

    def describe(self, **extra):
        return self.client.post("/api/v1/vision/", {"locale": "es-EC", "image": photo(), "profile": self.profile, **extra}, format="multipart")


@patch.dict(os.environ, PUBLIC)
class PublicAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.provider = Provider("Veo una superficie azul.")
        self.vision_client = patch("assistance.vision.httpx.Client", self.provider)
        self.vision_client.start()
        self.spark = patch("assistance.conversation.call_spark", return_value=ANSWER)
        self.call_spark = self.spark.start()

    def tearDown(self):
        self.vision_client.stop()
        self.spark.stop()
        bind_account(None)

    def test_a_new_account_uses_meta_with_its_own_grants_and_no_list(self):
        ana = Person("ana-nueva")
        self.assertEqual(ana.signup.status_code, 200, ana.signup.content)
        ana.own_profile()
        for purpose in ("meta_conversation", "camera_local", "meta_photos"):
            ana.decide(purpose, "grant")
        self.assertEqual(ana.converse().status_code, 200)
        self.call_spark.assert_called_once()
        described = ana.describe()
        self.assertEqual(described.status_code, 200, described.data)
        self.assertEqual(described.data["mode"], "meta")
        self.assertEqual(len(self.provider.sent), 1)
        self.assertNotIn("AINGEL_META_ALLOWED_USER_IDS", os.environ)

    def test_partial_grants_allow_conversation_but_not_photos(self):
        luis = Person("luis-parcial").own_profile()
        luis.decide("meta_conversation", "grant").decide("camera_local", "grant").decide("meta_photos", "decline")
        self.assertEqual(luis.converse().status_code, 200)
        refused = luis.describe()
        self.assertEqual(refused.data["error"], "privacy_review_required")
        self.assertEqual(self.provider.sent, [])  # the photo never left the server

    def test_nothing_without_a_decision(self):
        sara = Person("sara-sin-decidir").own_profile()
        self.assertEqual(sara.converse().data["error"], "privacy_review_required")
        self.assertEqual(sara.describe().data["error"], "privacy_review_required")
        self.call_spark.assert_not_called()
        self.assertEqual(self.provider.sent, [])

    def test_revoking_during_a_session_stops_sending(self):
        eva = Person("eva-revoca").own_profile()
        for purpose in ("camera_local", "meta_photos"):
            eva.decide(purpose, "grant")
        token = eva.describe().data["session"]
        eva.decide("meta_photos", "revoke")
        follow = eva.client.post("/api/v1/vision/", {"locale": "es-EC", "session": token, "question": "¿Y el fondo?"}, format="multipart")
        self.assertEqual((follow.status_code, follow.data["error"]), (409, "consent_changed"))
        self.assertEqual(len(self.provider.sent), 1)  # only the first description
        again = eva.client.post("/api/v1/vision/", {"locale": "es-EC", "session": token, "question": "¿Y el fondo?"}, format="multipart")
        self.assertEqual(again.data["error"], "visual_session_expired")  # the stored picture was deleted

    def test_minimum_age(self):
        refused = Person("sin-mayoria", adult=False)
        self.assertEqual(refused.signup.status_code, 400)
        self.assertEqual(refused.signup.json()["error"], "adult_declaration_required")

    def test_a_screen_needs_its_own_permission_not_the_cameras(self):
        rosa = Person("rosa-pantalla").own_profile()
        for purpose in ("camera_local", "meta_photos"):
            rosa.decide(purpose, "grant")
        refused = rosa.describe(source_kind="screen")
        self.assertEqual(refused.data["error"], "privacy_review_required")
        rosa.decide("meta_screen", "decline")
        self.assertEqual(rosa.describe(source_kind="screen").data["error"], "screen_consent_revoked")
        self.assertEqual(self.provider.sent, [])
        rosa.decide("meta_screen", "grant")
        self.assertEqual(rosa.describe(source_kind="screen").status_code, 200)
        self.assertEqual(len(self.provider.sent), 1)

    def test_documents_need_their_own_permission(self):
        pablo = Person("pablo-documentos").own_profile()
        for purpose in ("camera_local", "meta_photos"):
            pablo.decide(purpose, "grant")
        pdf = SimpleUploadedFile("libro.pdf", synthetic.document("book_pdf"), "application/pdf")
        opened = pablo.client.post("/api/v1/documents/", {"locale": "es-EC", "file": pdf, "profile": pablo.profile}, format="multipart")
        self.assertEqual(opened.data["error"], "privacy_review_required")
        pablo.decide("meta_documents", "grant")
        pdf = SimpleUploadedFile("libro.pdf", synthetic.document("book_pdf"), "application/pdf")
        opened = pablo.client.post("/api/v1/documents/", {"locale": "es-EC", "file": pdf, "profile": pablo.profile}, format="multipart")
        self.assertEqual(opened.status_code, 201, opened.data)

    def test_one_account_cannot_reach_another_accounts_profile(self):
        ana = Person("ana-propia").own_profile()
        ana.decide("meta_conversation", "grant")
        intruso = Person("intruso").own_profile()
        response = intruso.client.post(f"/api/v1/profiles/{ana.profile}/conversation/", {"turns": [{"role": "user", "text": "hola"}]}, format="json")
        self.assertEqual(response.status_code, 404)
        self.call_spark.assert_not_called()

    def test_each_account_is_counted_on_its_own_quota(self):
        """Through the real endpoints, every reservation names the account that made the request."""
        client = Mock()
        client.eval.return_value = 1
        fake = SimpleNamespace(make_key=lambda key: key, _cache=SimpleNamespace(get_client=lambda key, write: client))
        people = [Person(f"cuota-{index}").own_profile() for index in range(2)]
        for person in people:
            person.decide("camera_local", "grant").decide("meta_photos", "grant")
        with override_settings(PRODUCTION=True), patch("assistance.meta_quota.caches", {"meta_quota": fake}):
            for person in people:
                self.assertEqual(person.describe().status_code, 200)
        accounts = [next(arg for arg in call.args if isinstance(arg, str) and ":account:" in arg) for call in client.eval.call_args_list]
        self.assertEqual(len(accounts), 2)
        self.assertNotEqual(accounts[0], accounts[1])
        # And the platform's counters are the same for both: the per-account limit is not a platform limit.
        self.assertEqual(client.eval.call_args_list[0].args[2:4], client.eval.call_args_list[1].args[2:4])

    def test_one_description_at_a_time_per_account(self):
        lia = Person("lia-ocupada").own_profile()
        lia.decide("camera_local", "grant").decide("meta_photos", "grant")
        account = self.client_user_id(lia)
        cache.add(f"aingel:meta-slot:{account}", 1, 60)  # a description of hers is still running
        busy = lia.describe()
        self.assertEqual((busy.status_code, busy.data["error"]), (429, "meta_busy"))
        cache.delete(f"aingel:meta-slot:{account}")
        self.assertEqual(lia.describe().status_code, 200)

    def test_daily_spend_cap_is_per_account(self):
        caro = Person("caro-gasto").own_profile()
        caro.decide("camera_local", "grant").decide("meta_photos", "grant")
        otro = Person("otro-gasto").own_profile()
        otro.decide("camera_local", "grant").decide("meta_photos", "grant")
        MetaUsage.objects.create(feature="vision_standard", model="muse-spark-1.3", user_id=self.client_user_id(caro), cost_usd=Decimal("0.60"))
        with patch.dict(os.environ, {"AINGEL_META_USER_DAILY_USD": "0.50"}):
            self.assertEqual(caro.describe().data["error"], "meta_account_budget_exhausted")
            self.assertEqual(otro.describe().status_code, 200)

    @staticmethod
    def client_user_id(person):
        return person.client.get("/api/v1/auth/session/").json()["user"]["id"]
