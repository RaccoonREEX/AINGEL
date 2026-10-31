"""The browser speech-recognition decision belongs to one account: never inherited, revocable, tied to the notice."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from .consent import SPEECH_SERVICE_VERSION


class SpeechServiceDecisionTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        users.create_user(username="speech-first", password="Synthetic-Pass-123!")
        users.create_user(username="speech-second", password="Synthetic-Pass-456!")
        self.browser = Client()  # one browser, used by two people in turn

    def login(self, username, password):
        self.assertEqual(self.browser.post("/api/v1/auth/login/", {"username": username, "password": password},
                                           content_type="application/json").status_code, 200)
        return self.browser.get("/api/v1/auth/session/").json()["user"]

    def decide(self, accept, version=SPEECH_SERVICE_VERSION):
        return self.browser.post("/api/v1/auth/speech-service/", {"accept": accept, "version": version},
                                 content_type="application/json")

    def test_two_accounts_in_turn_on_the_same_browser_never_share_the_decision(self):
        self.assertFalse(self.login("speech-first", "Synthetic-Pass-123!")["speech_service"])
        self.assertTrue(self.decide(True).json()["user"]["speech_service"])
        self.browser.post("/api/v1/auth/logout/")
        self.assertIsNone(self.browser.get("/api/v1/auth/session/").json()["user"])
        # The next person on this browser is asked again: the first one's acceptance is theirs only.
        self.assertFalse(self.login("speech-second", "Synthetic-Pass-456!")["speech_service"])
        self.browser.post("/api/v1/auth/logout/")
        self.assertTrue(self.login("speech-first", "Synthetic-Pass-123!")["speech_service"])

    def test_withdrawal_and_a_new_notice_need_a_new_decision(self):
        self.login("speech-first", "Synthetic-Pass-123!")
        self.decide(True)
        self.assertFalse(self.decide(False).json()["user"]["speech_service"])
        self.decide(True)
        with patch("care.consent.SPEECH_SERVICE_VERSION", "2099-01-01"):
            self.assertFalse(self.browser.get("/api/v1/auth/session/").json()["user"]["speech_service"])

    def test_only_an_explicit_decision_on_the_current_notice_by_a_signed_in_account(self):
        self.assertEqual(self.decide(True).status_code, 401)
        self.login("speech-first", "Synthetic-Pass-123!")
        for body in ({"accept": "yes", "version": SPEECH_SERVICE_VERSION}, {"accept": True, "version": "old"}, {}):
            response = self.browser.post("/api/v1/auth/speech-service/", body, content_type="application/json")
            self.assertEqual(response.json()["error"], "speech_service_request_invalid")
        self.assertFalse(self.browser.get("/api/v1/auth/session/").json()["user"]["speech_service"])
