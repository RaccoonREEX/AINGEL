"""The person's own decisions about their data (care.consent), and the one-time code that lets an adult accept a
profile someone else set up for them, from their own account. A caregiver's help is never a decision."""

from datetime import timedelta
import hashlib
import secrets

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .consent import adult_declared, consent_state, decide
from .models import Profile, SubjectInvite
from .permissions import access, audit

CODE_HOURS = 48
DENIED = {"consent_subject_only", "legal_review_required", "adult_declaration_required"}


class ConsentCodeRate(ScopedRateThrottle):
    scope = "consent_code"


def code_hash(code):
    return hashlib.sha256(f"{settings.SECRET_KEY}:subject-invite:{code}".encode()).hexdigest()


@api_view(["GET", "POST"])
def consent(request, profile_id):
    profile = access(request.user, profile_id)
    locale = request.query_params.get("locale") if request.query_params.get("locale") in ("es-EC", "en-US") else profile.locale
    if request.method == "GET":
        return Response(consent_state(profile, request.user, locale))
    data = request.data
    if not isinstance(data, dict) or set(data) != {"purpose", "decision"}:
        return Response({"error": "consent_request_invalid"}, status=400)
    error = decide(profile, request.user, data["purpose"], data["decision"])
    if error:
        return Response({"error": error}, status=403 if error in DENIED else 400)
    audit(profile, request.user, f"consent.{data['decision']}", data["purpose"])
    profile.refresh_from_db()
    return Response(consent_state(profile, request.user, locale))


@api_view(["POST"])
@throttle_classes([ConsentCodeRate])
def invite(request, profile_id):
    """A new one-time code for the person (earlier unused codes stop working)."""
    profile = access(request.user, profile_id, "configure")
    if profile.subject_status != "pending_consent":
        return Response({"error": "consent_not_pending"}, status=400)
    code = f"{secrets.randbelow(10**8):08d}"
    with transaction.atomic():
        SubjectInvite.objects.filter(profile=profile, used_at__isnull=True).update(expires_at=timezone.now())
        item = SubjectInvite.objects.create(profile=profile, code_hash=code_hash(code), created_by=request.user,
                                            expires_at=timezone.now() + timedelta(hours=CODE_HOURS))
    audit(profile, request.user, "consent.code_created", item.id)
    return Response({"code": code, "expires_at": item.expires_at}, status=201)


@api_view(["POST"])
@throttle_classes([ConsentCodeRate])
def redeem(request):
    """The person links their own account to the profile set up for them; then they decide, purpose by purpose."""
    code = request.data.get("code") if isinstance(request.data, dict) else None
    if not isinstance(code, str) or not code.strip().isdigit() or len(code.strip()) != 8:
        return Response({"error": "consent_code_invalid"}, status=400)
    if not adult_declared(request.user):
        return Response({"error": "adult_declaration_required"}, status=403)
    with transaction.atomic():
        item = (SubjectInvite.objects.select_for_update().select_related("profile")
                .filter(code_hash=code_hash(code.strip()), used_at__isnull=True, expires_at__gt=timezone.now()).first())
        if item is None:
            return Response({"error": "consent_code_invalid"}, status=400)
        profile = Profile.objects.select_for_update().get(pk=item.profile_id)
        if profile.subject_status != "pending_consent":
            return Response({"error": "consent_not_pending"}, status=400)
        if profile.owner_id == request.user.id or profile.members.filter(user=request.user).exists():
            # Whoever set the profile up, or anyone in the circle, cannot accept as if they were the person.
            return Response({"error": "consent_subject_only"}, status=403)
        item.used_at = timezone.now()
        item.save(update_fields=["used_at"])
        profile.subject_user = request.user
        profile.subject_status = "subject_linked"
        profile.save(update_fields=["subject_user", "subject_status"])
    audit(profile, request.user, "consent.subject_linked", item.id)
    return Response({"profile": str(profile.pk), **consent_state(profile, request.user)}, status=200)


@api_view(["POST"])
def legal_review(request, profile_id):
    """The person cannot give consent: nothing is enabled until a reviewed legal basis is recorded by staff.
    No diagnosis implies this; it is a decision about this specific situation."""
    profile = access(request.user, profile_id, "configure")
    Profile.objects.filter(pk=profile.pk).update(subject_status="requires_legal_review", consent_epoch=F("consent_epoch") + 1)
    audit(profile, request.user, "consent.legal_review_requested")
    profile.refresh_from_db()
    return Response(consent_state(profile, request.user))
