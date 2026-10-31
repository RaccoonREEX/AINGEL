import cv2
from cryptography.fernet import InvalidToken
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from care.consent import granted, meta_account_denial, meta_allowed, private_media_allowed, refused, still_current, subject_account
from care.faces import family_matches
from care.permissions import access, audit

from . import synthetic
from .persona import profile_preferences
from .scene import SceneUnavailable, describe_scene, normalize_image
from .locate import locate_object


def health(request):
    return JsonResponse({"status": "ok", "service": "aingel-scaffold"})


class SceneRequest(serializers.Serializer):
    # A real photo, or the id of a server synthetic fixture (assistance.synthetic); never both.
    image = serializers.FileField(required=False)
    fixture = serializers.CharField(required=False, max_length=40)
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    private_test = serializers.BooleanField(default=False)
    # Profile whose person authorized camera + Meta for a real image.
    profile = serializers.UUIDField(required=False)
    # Also say which enrolled family members are in front (local OpenCV matching, care.faces).
    family = serializers.BooleanField(default=False)


# Fields that carry a real photo or personal context; none may go with a fixture.
REAL_FIELDS = ("image", "profile", "family", "private_test", "object_name")


def image_basis(request, values, kind="image"):
    """(path, fixture or error, profile): decided before any image is read or any provider request is built."""
    profile = access(request.user, values["profile"]) if "profile" in values else None
    if refused(profile, "camera_local"):
        return None, "camera_consent_revoked", None
    real = profile is not None and (
        private_media_allowed(profile, request.user, "image", values["private_test"]) or meta_allowed(profile, "image")
    )
    path, value = synthetic.route(request.data, kind, real, REAL_FIELDS)
    if path in ("real", "mock") and "image" not in values:
        return None, "image_required", None
    return path, value, profile if path == "real" else None


def basis_for(path):
    return {"fixture": synthetic.FIXTURE, "real": synthetic.REAL}.get(path)


def known_line(candidate, locale):
    name, relation = candidate["display_name"], candidate["relationship"].strip()
    if locale != "es-EC":
        return f"It looks like {name}" + (f" ({relation})" if relation else "") + "."
    # "Hijo" → «Parece ser tu hijo David»; longer free text would not read as a kinship word.
    return f"Parece ser tu {relation.lower()} {name}." if relation and len(relation.split()) <= 2 else f"Parece ser {name}."


def known_people(request, values, image):
    """Family members recognized in [image], for the owner or the person themselves, with the feature enabled and
    the person's own «face_local» grant. Recognition failing never blocks the description."""
    if not values["family"] or "profile" not in values:
        return []
    profile = access(request.user, values["profile"])
    subject = subject_account(profile)
    if request.user.id not in {profile.owner_id, subject.pk if subject else None} or not profile.face_recognition_enabled:
        return []
    if not granted(profile, ("face_local",)):
        return []
    try:
        found = family_matches(profile, image)
    except (ValidationError, ValueError, cv2.error, InvalidToken):
        return []
    audit(profile, request.user, "face.local_match_requested")
    people = {}
    for face in found:
        candidate = face["candidate"]
        if candidate and candidate["id"] not in people:
            people[candidate["id"]] = {**candidate, "line": known_line(candidate, values["locale"])}
    return list(people.values())


class SceneView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "scene"

    def post(self, request):
        if denial := meta_account_denial(request.user):
            return Response({"error": denial}, status=403)
        serializer = SceneRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        path, value, profile = image_basis(request, values)
        if path is None:
            return Response({"error": value}, status=403 if value == "camera_consent_revoked" else 400, headers={"Cache-Control": "no-store"})
        if path == "fixture":
            # The server's own picture and a fictitious profile; no family recognition.
            image, preferences, people = synthetic.image(value), synthetic.FICTIONAL_PREFERENCES, []
        else:
            try:
                image = normalize_image(values["image"])
            except ValueError as error:
                return Response({"error": str(error)}, status=400)
            # Own-media tests do not request local recognition of other people.
            people = known_people(request, values, image) if path == "real" and not values["private_test"] else []
            # The person's style preferences (and priority support only with their personalization grant).
            preferences = profile_preferences(profile.communication, meta_allowed(profile, "personalization")) if profile else None
        epoch = profile.consent_epoch if profile is not None else None
        try:
            result = describe_scene(image, values["locale"], basis_for(path), known_person=bool(people), preferences=preferences)
        except SceneUnavailable as error:
            return Response(
                {"error": str(error)}, status=503, headers={"Cache-Control": "no-store"}
            )
        if profile is not None and not still_current(profile, epoch):
            # Revoked while Meta was looking: the description is dropped, not shown as current.
            return Response({"error": "consent_changed"}, status=409, headers={"Cache-Control": "no-store"})
        result["people"] = people
        if path == "fixture":
            result["synthetic_fixture"] = value
        return Response(result, headers={"Cache-Control": "no-store"})


class LocateRequest(SceneRequest):
    object_name = serializers.CharField(max_length=80, required=False)

    def validate_object_name(self, value):
        if any(c in value for c in "<>|\n\r"):
            raise serializers.ValidationError("object_prompt_invalid")
        common = {
            "llaves": "keys",
            "gafas": "glasses",
            "lentes": "glasses",
            "cartera": "wallet",
            "teléfono": "phone",
            "taza": "cup",
            "círculo rojo": "red circle",
            "cuadrado azul": "blue square",
        }
        return common.get(value.strip().casefold(), value.strip())


class LocateView(SceneView):
    def post(self, request):
        if denial := meta_account_denial(request.user):
            return Response({"error": denial}, status=403)
        serializer = LocateRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        # A fixture here names the object (assistance.synthetic.OBJECTS) in the server's shapes picture.
        path, value, profile = image_basis(request, values, "object")
        if path is None:
            return Response({"error": value}, status=403 if value == "camera_consent_revoked" else 400)
        if path == "fixture":
            image, prompt = synthetic.image("shapes"), synthetic.OBJECTS[value]["prompt"]
        else:
            if "object_name" not in values:
                return Response({"error": "object_prompt_invalid"}, status=400)
            try:
                image = normalize_image(values["image"])
            except ValueError as error:
                return Response({"error": str(error)}, status=400)
            prompt = values["object_name"]
        epoch = profile.consent_epoch if profile is not None else None
        try:
            result = locate_object(image, prompt, basis_for(path))
        except SceneUnavailable as error:
            return Response({"error": str(error)}, status=503)
        if profile is not None and not still_current(profile, epoch):
            return Response({"error": "consent_changed"}, status=409)
        if path == "fixture":
            result["synthetic_fixture"] = value
        return Response(result)
