import base64
import io
import json
import secrets
import time

from django.contrib.auth import get_user_model, login, logout
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
import pyotp
import qrcode
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.decorators import throttle_classes

from .crypto import decrypt, encrypt
from .models import MFADevice


class MFARate(UserRateThrottle):
    scope = "mfa"


def consume_code(device, code):
    if not isinstance(code, str) or len(code) > 100:
        return False
    if len(code) == 6 and code.isdigit():
        totp = pyotp.TOTP(decrypt(device.secret_encrypted))
        counter = int(time.time() // 30)
        for offset in [-1, 0, 1]:
            current = counter + offset
            if current > device.last_counter and constant_time_compare(
                totp.at(current * 30), code
            ):
                device.last_counter = current
                return True
    digest = salted_hmac("aingel-recovery", code).hexdigest()
    for saved in device.recovery_hashes:
        if constant_time_compare(saved, digest):
            device.recovery_hashes = [x for x in device.recovery_hashes if x != saved]
            return True
    return False


def begin_challenge(request, user):
    if request.user.is_authenticated:
        logout(request)
    request.session.cycle_key()
    request.session["mfa_pending_user"] = user.pk
    request.session["mfa_pending_until"] = int(time.time()) + 300
    return JsonResponse(
        {"mfa_required": True, "user": None, "csrf": get_token(request)}
    )


@csrf_protect
@require_http_methods(["POST"])
def verify_challenge(request):
    user_id = request.session.get("mfa_pending_user")
    if not user_id or request.session.get("mfa_pending_until", 0) < time.time():
        return JsonResponse({"error": "mfa_challenge_expired"}, status=400)
    rate_key = f"mfa:{user_id}"
    cache.add(rate_key, 0, 300)
    if cache.incr(rate_key) > 6:
        return JsonResponse({"error": "mfa_rate_limited"}, status=429)
    try:
        data = json.loads(request.body)
        code = data.get("code", "").strip()
    except (ValueError, TypeError, AttributeError):
        return JsonResponse({"error": "mfa_code_invalid"}, status=400)
    with transaction.atomic():
        device = (
            MFADevice.objects.select_for_update()
            .filter(user_id=user_id, enabled=True, user__is_active=True)
            .select_related("user")
            .first()
        )
        if not device or not consume_code(device, code):
            return JsonResponse({"error": "mfa_code_invalid"}, status=400)
        device.save(update_fields=["last_counter", "recovery_hashes"])
    request.session.pop("mfa_pending_user", None)
    request.session.pop("mfa_pending_until", None)
    login(request, device.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["mfa_epoch"] = device.epoch
    from .auth import session_data

    return JsonResponse(session_data(request))


def check_password(request):
    value = request.data.get("password", "")
    if not isinstance(value, str) or not request.user.check_password(value):
        raise PermissionDenied("current_password_required")


@api_view(["GET"])
def mfa_status(request):
    device = MFADevice.objects.filter(user=request.user).first()
    return Response(
        {
            "enabled": bool(device and device.enabled),
            "recovery_remaining": (
                len(device.recovery_hashes) if device and device.enabled else 0
            ),
        }
    )


@api_view(["POST"])
@throttle_classes([MFARate])
def mfa_setup(request):
    check_password(request)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        device, _ = MFADevice.objects.get_or_create(user=request.user)
        if device.enabled:
            raise ValidationError("mfa_already_enabled")
        secret = pyotp.random_base32()
        device.pending_encrypted = encrypt(secret)
        device.pending_at = timezone.now()
        device.save()
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=request.user.username, issuer_name="AINGEL"
    )
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(
        {
            "secret": secret,
            "qr_png": "data:image/png;base64,"
            + base64.b64encode(buffer.getvalue()).decode(),
            "expires_in": 600,
        }
    )


@api_view(["POST"])
@throttle_classes([MFARate])
def mfa_enable(request):
    with transaction.atomic():
        device = (
            MFADevice.objects.select_for_update()
            .filter(user=request.user, enabled=False)
            .first()
        )
        if (
            not device
            or not device.pending_at
            or (timezone.now() - device.pending_at).total_seconds() > 600
        ):
            raise ValidationError("mfa_setup_expired")
        code = request.data.get("code", "")
        if (
            not isinstance(code, str)
            or len(code) != 6
            or not code.isascii()
            or not code.isdigit()
        ):
            raise ValidationError("mfa_code_invalid")
        # Take one clock snapshot for both verification and the replay counter.
        # A 30-second boundary between two reads must not turn a valid code into a 500.
        counter = int(time.time() // 30)
        totp = pyotp.TOTP(decrypt(device.pending_encrypted))
        matched = next(
            (
                c
                for c in [counter - 1, counter, counter + 1]
                if constant_time_compare(totp.at(c * 30), code)
            ),
            None,
        )
        if matched is None:
            raise ValidationError("mfa_code_invalid")
        device.secret_encrypted = device.pending_encrypted
        device.pending_encrypted = ""
        device.pending_at = None
        device.enabled = True
        device.epoch += 1
        device.last_counter = matched
        codes = [secrets.token_hex(8) for _ in range(8)]
        device.recovery_hashes = [
            salted_hmac("aingel-recovery", x).hexdigest() for x in codes
        ]
        device.save()
        request.session["mfa_epoch"] = device.epoch
    return Response({"enabled": True, "recovery_codes": codes})


@api_view(["POST"])
@throttle_classes([MFARate])
def mfa_disable(request):
    check_password(request)
    with transaction.atomic():
        device = (
            MFADevice.objects.select_for_update()
            .filter(user=request.user, enabled=True)
            .first()
        )
        if not device or not consume_code(device, request.data.get("code", "")):
            raise ValidationError("mfa_code_invalid")
        device.enabled = False
        device.secret_encrypted = ""
        device.recovery_hashes = []
        device.pending_encrypted = ""
        device.pending_at = None
        device.epoch += 1
        device.save()
        request.session["mfa_epoch"] = device.epoch
    return Response({"enabled": False})


class MFAEpochMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            device = MFADevice.objects.filter(user=request.user).only("epoch").first()
            if (
                device
                and device.epoch > 0
                and request.session.get("mfa_epoch") != device.epoch
            ):
                logout(request)
        return self.get_response(request)
