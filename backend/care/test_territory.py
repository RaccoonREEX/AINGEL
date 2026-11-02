"""Meta's Restricted Territories (care.territory): no account is created for, and no Meta feature serves, a person who
declares being located in one; eligible accounts keep general access with no approval and no list of accounts."""

import os
from unittest.mock import AsyncMock, patch

from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from assistance.meta_quota import bind_account
from assistance.test_captions import FakeMeta as FakeVoice
from config.asgi import application

from . import territory
from .consent import TERMS_VERSION
from .models import AccountPolicy, Profile
from .testing import adult, authorize

PUBLIC = {"AINGEL_AI_MODE": "meta", "MODEL_API_KEY": "test-key", "AINGEL_REAL_DATA": "1",
          "AINGEL_SYNTHETIC_TESTS_ONLY": "0", "AINGEL_PRIVATE_OWN_MEDIA_TEST": "0"}
ANSWER = {"mode": "meta", "model": "muse-spark-1.3", "text": "Respuesta de prueba."}
PROXY = {"AINGEL_GEO_COUNTRY_HEADER": "X-AINGEL-Country"}


def signup(username, located=territory.OUTSIDE, version=territory.POLICY_VERSION, **headers):
    body = {"username": username, "password": "Una-clave-de-prueba-larga-2026", "adult": True, "terms_version": TERMS_VERSION}
    if located is not None:
        body |= {"territory": located, "territory_version": version}
    client = APIClient()
    return client, client.post("/api/v1/auth/register/", body, format="json", **headers)


@patch.dict(os.environ, PUBLIC)
class TerritoryTests(TestCase):
    def setUp(self):
        cache.clear()
        self.spark = patch("assistance.conversation.call_spark", return_value=ANSWER)
        self.call_spark = self.spark.start()

    def tearDown(self):
        self.spark.stop()
        bind_account(None)

    def eligible(self, username):
        user = adult(get_user_model().objects.create_user(username=username))
        profile = authorize(Profile.objects.create(owner=user, display_name="Ficticio"), meta_conversation=True)
        client = APIClient()
        client.force_authenticate(user)
        return user, profile, client

    def ask(self, client, profile, **headers):
        return client.post(f"/api/v1/profiles/{profile.pk}/conversation/", {"turns": [{"role": "user", "text": "hola"}]}, format="json", **headers)

    def test_no_account_is_created_for_someone_inside_a_restricted_territory(self):
        _, response = signup("dentro", located=territory.INSIDE)
        self.assertEqual((response.status_code, response.json()), (403, {"error": "territory_restricted"}))
        self.assertFalse(get_user_model().objects.filter(username="dentro").exists())

    def test_sign_up_needs_the_declaration_for_the_current_policy(self):
        for located, version in ((None, None), ("somewhere", territory.POLICY_VERSION), (territory.OUTSIDE, "2025-01-01")):
            with self.subTest(located=located, version=version):
                _, response = signup("sin-declarar", located=located, version=version)
                self.assertEqual((response.status_code, response.json()), (400, {"error": "territory_declaration_required"}))
        self.assertFalse(get_user_model().objects.filter(username="sin-declarar").exists())

    def test_an_eligible_person_signs_up_and_uses_meta_without_approval(self):
        client, response = signup("fuera")
        self.assertEqual(response.status_code, 200, response.content)
        session = response.json()
        self.assertEqual(session["user"]["territory"], territory.OUTSIDE)
        self.assertEqual(session["territory_version"], territory.POLICY_VERSION)
        self.assertIn("Venezuela", session["restricted_territories"]["es-EC"])
        policy = AccountPolicy.objects.get(user__username="fuera")
        self.assertEqual(policy.territory, territory.OUTSIDE)  # only the answer: no country, no location
        profile = client.post("/api/v1/profiles/", {"display_name": "Yo", "locale": "es-EC", "for_self": True}, format="json").data["id"]
        client.post(f"/api/v1/profiles/{profile}/consent/", {"purpose": "meta_conversation", "decision": "grant"}, format="json")
        answered = client.post(f"/api/v1/profiles/{profile}/conversation/", {"turns": [{"role": "user", "text": "hola"}]}, format="json")
        self.assertEqual(answered.status_code, 200, answered.data)
        self.call_spark.assert_called_once()

    def test_an_existing_account_declares_and_inside_closes_meta_until_it_changes(self):
        user, profile, client = self.eligible("se-muda")
        AccountPolicy.objects.filter(user=user).update(territory="", territory_version="")  # from before this policy
        self.assertEqual(self.ask(client, profile).data, {"error": "territory_declaration_required"})
        session = APIClient()
        session.force_login(user)
        self.assertEqual(session.post("/api/v1/auth/territory/", {"territory": "inside_restricted"}, format="json").status_code, 400)
        inside = session.post("/api/v1/auth/territory/", {"territory": "inside_restricted", "territory_version": territory.POLICY_VERSION}, format="json")
        self.assertEqual(inside.json()["user"]["territory"], territory.INSIDE)
        refused = self.ask(client, profile)
        self.assertEqual((refused.status_code, refused.data), (403, {"error": "meta_territory_restricted"}))
        self.call_spark.assert_not_called()
        self.assertEqual(client.get("/api/v1/profiles/").status_code, 200)  # the account itself is not deleted
        session.post("/api/v1/auth/territory/", {"territory": "outside_restricted", "territory_version": territory.POLICY_VERSION}, format="json")
        self.assertEqual(self.ask(client, profile).status_code, 200)

    def test_an_outdated_policy_version_asks_again(self):
        user, profile, client = self.eligible("version-vieja")
        AccountPolicy.objects.filter(user=user).update(territory_version="2025-01-01")
        self.assertEqual(self.ask(client, profile).data, {"error": "territory_declaration_required"})

    def test_the_proxy_country_refuses_restricted_countries_when_configured(self):
        _, profile, client = self.eligible("por-red")
        # Not configured: the header is ignored (a client cannot set it in place of the proxy).
        self.assertEqual(self.ask(client, profile, HTTP_X_AINGEL_COUNTRY="VE").status_code, 200)
        with patch.dict(os.environ, PROXY):
            refused = self.ask(client, profile, HTTP_X_AINGEL_COUNTRY="ve")
            self.assertEqual((refused.status_code, refused.data), (403, {"error": "meta_territory_restricted"}))
            self.assertEqual(self.ask(client, profile, HTTP_X_AINGEL_COUNTRY="EC").status_code, 200)
            self.assertEqual(self.ask(client, profile).status_code, 200)  # no country known: the declaration decides
            _, response = signup("desde-red", HTTP_X_AINGEL_COUNTRY="CU")
            self.assertEqual((response.status_code, response.json()), (403, {"error": "territory_restricted"}))
        self.assertEqual(self.call_spark.call_count, 3)

    def test_eligible_accounts_need_no_list(self):
        self.assertNotIn("AINGEL_META_ALLOWED_USER_IDS", os.environ)
        for name in ("uno", "dos", "tres"):
            _, profile, client = self.eligible(f"general-{name}")
            self.assertEqual(self.ask(client, profile).status_code, 200)

    def test_local_mode_does_not_ask_for_meta_rules(self):
        user, profile, client = self.eligible("modo-local")
        AccountPolicy.objects.filter(user=user).update(territory="", territory_version="")
        with patch.dict(os.environ, {"AINGEL_AI_MODE": "mock", "AINGEL_REAL_DATA": "0", "AINGEL_SYNTHETIC_TESTS_ONLY": "1"}):
            response = client.post(f"/api/v1/profiles/{profile.pk}/conversation/", {"fixture": "greeting"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)


@patch.dict(os.environ, {**PUBLIC, **PROXY})
class TerritoryCaptionTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.user = adult(get_user_model().objects.create_user(username="voz-territorio"))
        self.profile = authorize(Profile.objects.create(owner=self.user, display_name="Voz"), {"microphone": True, "meta_data": True})
        self.client.force_login(self.user)
        self.cookie = f"sessionid={self.client.cookies['sessionid'].value}".encode()

    async def start(self, country):
        headers = [(b"origin", b"http://127.0.0.1:5173"), (b"cookie", self.cookie)]
        if country:
            headers.append((b"x-aingel-country", country))
        ws = WebsocketCommunicator(application, "/ws/captions/", headers=headers)
        self.assertTrue((await ws.connect())[0])
        await ws.send_json_to({"type": "start", "locale": "es-EC", "profile": str(self.profile.pk)})
        reply = await ws.receive_json_from()
        await ws.disconnect()
        return reply

    async def test_captions_from_a_restricted_country_never_reach_meta(self):
        with patch("assistance.captions.connect", new=AsyncMock(return_value=FakeVoice())) as connect:
            self.assertEqual(await self.start(b"RU"), {"type": "error", "code": "meta_territory_restricted"})
            connect.assert_not_called()
            self.assertEqual((await self.start(b"EC"))["type"], "ready")
