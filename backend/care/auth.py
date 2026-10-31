import json
import time

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .consent import SPEECH_SERVICE_VERSION, TERMS_VERSION, adult_declared, decide_speech_service, declare_adult, speech_service_accepted


def session_data(request):
    return {
        "user": (
            {"id": request.user.id, "username": request.user.username, "adult_declared": adult_declared(request.user),
             "speech_service": speech_service_accepted(request.user)}
            if request.user.is_authenticated
            else None
        ),
        "csrf": get_token(request),
        # Current terms the 18+ declaration refers to (care.consent): clients show and send it back.
        "terms_version": TERMS_VERSION,
        "speech_service_version": SPEECH_SERVICE_VERSION,
        "mfa_required": bool(
            request.session.get("mfa_pending_user")
            and request.session.get("mfa_pending_until", 0) > time.time()
        ),
    }


@require_http_methods(["GET"])
def session(request):
    return JsonResponse(session_data(request))


@csrf_protect
@require_http_methods(["POST"])
def authenticate_user(request, register=False):
    # Loopback development has no reverse proxy; do not trust X-Forwarded-For.
    rate_key = "auth:" + request.META.get("REMOTE_ADDR", "unknown")
    cache.add(rate_key, 0, 300)
    if cache.incr(rate_key) > 15:
        return JsonResponse({"error": "auth_rate_limited"}, status=429)
    try:
        data = json.loads(request.body)
        username = data.get("username", "").strip().lower()
        password = data.get("password", "")
        if (
            not isinstance(password, str)
            or len(password) > 256
            or not username
            or len(username) > 150
        ):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "credentials_invalid"}, status=400)
    if register and not adult_statement(data):
        # Only adults (18+) may hold an account: required by the Meta Model API terms, checked here, not only in the apps.
        return JsonResponse({"error": "adult_declaration_required"}, status=400)
    if register:
        user = get_user_model()(username=username)
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
            user.set_password(password)
            user.save()
            declare_adult(user, TERMS_VERSION)
        except (ValidationError, IntegrityError):
            return JsonResponse({"error": "registration_invalid"}, status=400)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    else:
        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse({"error": "credentials_invalid"}, status=400)
        from .models import MFADevice
        from .mfa import begin_challenge

        device = MFADevice.objects.filter(user=user).first()
        if device and device.enabled:
            return begin_challenge(request, user)
        login(request, user)
        if device:
            request.session["mfa_epoch"] = device.epoch
    # A previously initiated challenge belongs only to its original password
    # attempt, never to a different account subsequently signed in here.
    request.session.pop("mfa_pending_user", None)
    request.session.pop("mfa_pending_until", None)
    return JsonResponse(session_data(request))


def adult_statement(data):
    """An explicit «I am 18 or older» for the current terms; a self-declaration, not identity verification."""
    return isinstance(data, dict) and data.get("adult") is True and data.get("terms_version") == TERMS_VERSION


@csrf_protect
@require_http_methods(["POST"])
def declare(request):
    """Accounts created before the age policy declare it here before using AINGEL with Meta."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    try:
        data = json.loads(request.body)
    except ValueError:
        data = None
    if not adult_statement(data):
        return JsonResponse({"error": "adult_declaration_required"}, status=400)
    declare_adult(request.user, TERMS_VERSION)
    return JsonResponse(session_data(request))


@csrf_protect
@require_http_methods(["POST"])
def speech_service(request):
    """The signed-in account accepts (for the current notice) or withdraws that the browser's speech recognition may
    send their voice to its vendor. Never inferred, never shared between accounts."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "authentication_required"}, status=401)
    try:
        data = json.loads(request.body)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("accept"), bool) or (
        data["accept"] and data.get("version") != SPEECH_SERVICE_VERSION
    ):
        return JsonResponse({"error": "speech_service_request_invalid"}, status=400)
    decide_speech_service(request.user, data["accept"])
    return JsonResponse(session_data(request))


@csrf_protect
@require_http_methods(["POST"])
def sign_out(request):
    logout(request)
    return JsonResponse(session_data(request))


class PrivateAPIResponses:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/"):
            response["Cache-Control"] = "no-store"
            response["Pragma"] = "no-cache"
        return response
