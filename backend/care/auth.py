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


def session_data(request):
    return {
        "user": (
            {"id": request.user.id, "username": request.user.username}
            if request.user.is_authenticated
            else None
        ),
        "csrf": get_token(request),
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
    if register:
        user = get_user_model()(username=username)
        try:
            user.full_clean(exclude=["password"])
            validate_password(password, user)
            user.set_password(password)
            user.save()
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
