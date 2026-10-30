import cv2
from cryptography.fernet import InvalidToken
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from care.consent import meta_allowed, private_media_allowed, synthetic_allowed
from care.faces import family_matches
from care.permissions import access, audit

from .scene import SceneUnavailable, describe_scene, normalize_image
from .locate import locate_object


def health(request):
    return JsonResponse({"status": "ok", "service": "aingel-scaffold"})


class SceneRequest(serializers.Serializer):
    image = serializers.FileField()
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    synthetic = serializers.BooleanField(default=False)
    private_test = serializers.BooleanField(default=False)
    # Profile whose sign-up authorizations (camera + Meta) cover a real image.
    profile = serializers.UUIDField(required=False)
    # Also say which enrolled family members are in front (local OpenCV matching, care.faces).
    family = serializers.BooleanField(default=False)


def image_allowed(request, values):
    """Synthetic test, or a real image of a profile the user can access that authorized camera and Meta."""
    if synthetic_allowed(values["synthetic"]):
        return True
    if "profile" not in values:
        return False
    profile = access(request.user, values["profile"])
    return private_media_allowed(profile, request.user, "image", values["private_test"]) or meta_allowed(profile, "image")


def known_line(candidate, locale):
    name, relation = candidate["display_name"], candidate["relationship"].strip()
    if locale != "es-EC":
        return f"It looks like {name}" + (f" ({relation})" if relation else "") + "."
    # "Hijo" → «Parece ser tu hijo David»; longer free text would not read as a kinship word.
    return f"Parece ser tu {relation.lower()} {name}." if relation and len(relation.split()) <= 2 else f"Parece ser {name}."


def known_people(request, values, image):
    """Family members recognized in [image], only for the profile owner with the feature enabled.
    Recognition failing never blocks the description."""
    if not values["family"] or "profile" not in values:
        return []
    profile = access(request.user, values["profile"])
    if profile.owner_id != request.user.id or not profile.face_recognition_enabled:
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
        serializer = SceneRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            image = normalize_image(values["image"])
        except ValueError as error:
            return Response({"error": str(error)}, status=400)
        allowed = image_allowed(request, values)
        # Own-media tests do not request local recognition of other people.
        people = known_people(request, values, image) if allowed and not values["private_test"] else []
        try:
            result = describe_scene(image, values["locale"], allowed, known_person=bool(people))
        except SceneUnavailable as error:
            return Response(
                {"error": str(error)}, status=503, headers={"Cache-Control": "no-store"}
            )
        result["people"] = people
        return Response(result, headers={"Cache-Control": "no-store"})


class LocateRequest(SceneRequest):
    object_name = serializers.CharField(max_length=80)

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
        serializer = LocateRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            image = normalize_image(values["image"])
        except ValueError as error:
            return Response({"error": str(error)}, status=400)
        try:
            return Response(
                locate_object(image, values["object_name"], image_allowed(request, values))
            )
        except SceneUnavailable as error:
            return Response({"error": str(error)}, status=503)
