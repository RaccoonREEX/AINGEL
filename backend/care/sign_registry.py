"""The sign registry (AINGEL 3.0, phase 5): every sign AINGEL's hands can make, with its source, licence, regional
variant and validation status in a sign language.

A sign is «validated» only by people, never by this code: at least two approvals of the same animation fingerprint
(web/src/components/aingel/signFingerprint.ts), at least one of them by a Deaf signer of the language, and no later
review of that fingerprint asking for changes. Clients compare the validated fingerprint with the animation they
would play; a changed animation is «pending» again. Until then the apps show full subtitles and say that sign
interpretation is not available, and play AINGEL's own designs only when the person asks for them as
illustrations.

Reviews are data in care/data/sign_registry.json, added with `manage.py record_sign_review` and committed through a
reviewed change, so who validated what stays visible. No grammar transformation is applied until a rule is recorded
here with its source.
"""

import json
import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from rest_framework import serializers
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

REGISTRY = Path(__file__).resolve().parent / "data" / "sign_registry.json"
LANGUAGES = {"lsec": "Lengua de Señas Ecuatoriana"}
KINDS = ("word", "letter", "number")
ROLES = ("deaf_signer", "interpreter", "linguist", "hearing_signer")
DECISIONS = ("approve", "changes_requested", "reject")
FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
SIGN_ID = re.compile(r"[a-zñ0-9_]{1,40}\Z")


class InvalidRegistry(Exception):
    pass


class FeedbackRate(UserRateThrottle):
    scope = "sign_feedback"


def kind_of(sign_id):
    if re.fullmatch(r"n\d+", sign_id):
        return "number"
    return "letter" if len(sign_id) == 1 else "word"


def _text(value, limit, required=True):
    if value is None and not required:
        return True
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def validate(data):
    """Raises InvalidRegistry unless [data] has the registry's shape (checked on every load)."""
    try:
        if data.get("version") != 1 or data.get("language") not in LANGUAGES:
            raise ValueError("header")
        if not isinstance(data.get("grammar_rules"), list):
            raise ValueError("grammar_rules")
        for rule in data["grammar_rules"]:
            if not (_text(rule.get("id"), 60) and _text(rule.get("description"), 500) and _text(rule.get("source"), 300)):
                raise ValueError("grammar rule without a source")
        signs = data.get("signs")
        if not isinstance(signs, dict) or not signs:
            raise ValueError("signs")
        for sign_id, entry in signs.items():
            if not SIGN_ID.fullmatch(sign_id) or entry.get("kind") not in KINDS:
                raise ValueError(sign_id)
            if not (_text(entry.get("source"), 300) and _text(entry.get("license"), 200)):
                raise ValueError(sign_id + ": source and licence")
            if not (_text(entry.get("region"), 100, required=False) and _text(entry.get("non_manual"), 500, required=False)):
                raise ValueError(sign_id + ": region or non-manual")
            for review in entry.get("reviews", []):
                if review.get("role") not in ROLES or review.get("decision") not in DECISIONS:
                    raise ValueError(sign_id + ": review role or decision")
                if not FINGERPRINT.fullmatch(str(review.get("fingerprint", ""))):
                    raise ValueError(sign_id + ": review fingerprint")
                if not (_text(review.get("reviewer"), 120) and _text(review.get("region"), 100)):
                    raise ValueError(sign_id + ": reviewer and region")
                if not _text(review.get("notes"), 1000, required=False):
                    raise ValueError(sign_id + ": notes")
                date.fromisoformat(review.get("date", ""))
    except (AttributeError, TypeError, ValueError) as error:
        raise InvalidRegistry(str(error)) from None
    return data


@lru_cache(maxsize=1)
def load():
    return validate(json.loads(REGISTRY.read_text(encoding="utf-8")))


def status(entry):
    """(status, fingerprint, regions) of a sign from its reviews: «validated» with the fingerprint and regions the
    approvals cover, «changes_requested», «in_review» or «pending»."""
    reviews = sorted(entry.get("reviews", []), key=lambda review: review["date"])
    if not reviews:
        return "pending", None, []
    latest = reviews[-1]["fingerprint"]
    current = [review for review in reviews if review["fingerprint"] == latest]
    last_approval = max((r["date"] for r in current if r["decision"] == "approve"), default=None)
    blocking = [r for r in current if r["decision"] != "approve" and (last_approval is None or r["date"] >= last_approval)]
    if blocking:
        return ("rejected" if blocking[-1]["decision"] == "reject" else "changes_requested"), None, []
    approvals = [r for r in current if r["decision"] == "approve"]
    if len(approvals) >= 2 and any(r["role"] == "deaf_signer" for r in approvals):
        return "validated", latest, sorted({r["region"] for r in approvals})
    return "in_review", None, []


def public():
    data = load()
    signs = {}
    for sign_id, entry in data["signs"].items():
        state, fingerprint, regions = status(entry)
        signs[sign_id] = {
            "kind": entry["kind"], "status": state, "fingerprint": fingerprint, "regions": regions,
            "source": entry["source"], "license": entry["license"], "region": entry.get("region"),
            "non_manual": entry.get("non_manual"), "reviews": len(entry.get("reviews", [])),
        }
    validated = sum(1 for sign in signs.values() if sign["status"] == "validated")
    return {
        "version": data["version"], "language": data["language"], "language_name": LANGUAGES[data["language"]],
        "signs": signs, "grammar_rules": data["grammar_rules"],
        "summary": {"total": len(signs), "validated": validated},
    }


def validated_ids():
    return {sign_id for sign_id, entry in load()["signs"].items() if status(entry)[0] == "validated"}


@api_view(["GET"])
def registry(request):
    """What each sign is and whether people who sign the language validated it (no personal data of reviewers
    beyond the count; names stay in the reviewed data file)."""
    return Response(public())


class FeedbackRequest(serializers.Serializer):
    sign = serializers.CharField(max_length=40)
    fingerprint = serializers.RegexField(r"^[0-9a-f]{64}$", required=False)
    verdict = serializers.ChoiceField(choices=["correct", "incorrect", "unclear", "regional_variant"])
    role = serializers.ChoiceField(choices=["deaf_signer", "interpreter", "hearing_signer", "learner", "other"])
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_sign(self, value):
        if value not in load()["signs"]:
            raise serializers.ValidationError("sign_unknown")
        return value


@api_view(["POST"])
@throttle_classes([FeedbackRate])
def feedback(request):
    """A correction from a Deaf user or an expert: kept for the reviewers, it changes nothing by itself."""
    from .models import SignFeedback

    serializer = FeedbackRequest(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    SignFeedback.objects.create(
        user=request.user, sign=values["sign"], language=load()["language"], fingerprint=values.get("fingerprint", ""),
        verdict=values["verdict"], role=values["role"], region=values.get("region", "").strip(),
        comment=values.get("comment", "").strip(),
    )
    return Response({"recorded": True}, status=201)
