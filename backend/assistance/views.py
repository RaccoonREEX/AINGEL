import cv2
from cryptography.fernet import InvalidToken
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from care.consent import capture_refusal, granted, meta_account_denial, meta_allowed, private_media_allowed, refused, still_current, subject_account
from care.faces import FaceConsentChanged, FaceRecognitionDisabled, family_matches, recognition_enabled
from care.permissions import access, audit

from . import synthetic, vision
from .persona import profile_preferences
from .scene import SceneUnavailable, describe_scene, normalize_image
from .locate import locate_object
from .meta_quota import MetaQuotaError, meta_slot


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


# Refusals of a capture purpose: 403, before anything is read.
REFUSALS = ("camera_consent_revoked", "screen_consent_revoked", "document_consent_revoked")


def image_basis(request, values, kind="image", content=REAL_FIELDS, media="image"):
    """(path, fixture or error, profile): decided before any image is read or any provider request is built.
    [media]: «image» (camera or gallery photo) or «screen» (a capture of the person's computer screen), each under
    its own purposes (care.consent.NEEDS)."""
    profile = access(request.user, values["profile"]) if "profile" in values else None
    if refusal := capture_refusal(profile, media):
        return None, refusal, None
    real = profile is not None and (
        private_media_allowed(profile, request.user, media, values["private_test"]) or meta_allowed(profile, media)
    )
    path, value = synthetic.route(request.data, kind, real, content)
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
    the person's own «face_local» grant. Recognition failing never blocks the description. With the server switch off
    (care.faces, hotfix) nothing is looked up or processed."""
    if not recognition_enabled() or not values["family"] or "profile" not in values:
        return []
    profile = access(request.user, values["profile"])
    subject = subject_account(profile)
    if request.user.id not in {profile.owner_id, subject.pk if subject else None} or not profile.face_recognition_enabled:
        return []
    if not granted(profile, ("face_local",)):
        return []
    try:
        found = family_matches(profile, image)
    except (FaceRecognitionDisabled, FaceConsentChanged, ValidationError, ValueError, cv2.error, InvalidToken):
        return []  # off, not authorized, or revoked while processing: no one is named
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


class VisionRequest(SceneRequest):
    """Deep vision (assistance.vision). Each optional field overrides what the question suggests."""
    question = serializers.CharField(max_length=600, required=False)
    detail_level = serializers.ChoiceField(choices=list(vision.LEVELS), required=False)
    visual_task = serializers.ChoiceField(choices=["auto", *vision.TASKS], required=False)
    focus_region = serializers.ChoiceField(choices=list(vision.REGIONS), required=False)
    source_kind = serializers.ChoiceField(choices=list(vision.SOURCES), default="camera")
    # A follow-up about the image of an earlier answer, instead of a new image or fixture.
    session = serializers.CharField(max_length=64, required=False)

    def validate_question(self, value):
        if any(c in value for c in "<>\x00"):
            raise serializers.ValidationError("question_invalid")
        return value.strip()


def asked(values):
    """What the person asked, as remembered in a follow-up session: their words, or the part they pointed at."""
    region = values.get("focus_region")
    return values.get("question") or (f"the {vision.REGION_NAMES.get(region, region)} part" if region else "a description")


# A typed question is free content: like a photo, it never goes with a server fixture.
VISION_FIELDS = REAL_FIELDS + ("question",)
NO_STORE = {"Cache-Control": "no-store"}


class VisionView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "vision"

    def post(self, request):
        if denial := meta_account_denial(request.user):
            return Response({"error": denial}, status=403, headers=NO_STORE)
        serializer = VisionRequest(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        if "session" in values:
            return self.follow_up(request, values)
        media = "screen" if values["source_kind"] == "screen" else "image"
        path, value, profile = image_basis(request, values, content=VISION_FIELDS, media=media)
        if path is None:
            return Response({"error": value}, status=403 if value in REFUSALS else 400, headers=NO_STORE)
        if path == "fixture":
            image, preferences = synthetic.image(value), synthetic.FICTIONAL_PREFERENCES
        else:
            try:
                image = normalize_image(values["image"], side=2048)
            except ValueError as error:
                return Response({"error": str(error)}, status=400, headers=NO_STORE)
            preferences = profile_preferences(profile.communication, meta_allowed(profile, "personalization")) if profile else None
        epoch = profile.consent_epoch if profile is not None else None
        response = self.answer(request, values, image, basis_for(path), preferences, profile, epoch)
        if response.status_code == 200:
            response.data["session"] = vision.open_session(
                request.user, image, basis_for(path), values["locale"], response.data["task"], asked(values),
                response.data["text"], profile=profile, epoch=epoch,
                fixture=value if path == "fixture" else None, private_test=values["private_test"], media=media,
            )
            response.data["session_seconds"] = vision.SESSION_SECONDS
            if path == "fixture":
                response.data["synthetic_fixture"] = value
        return response

    def follow_up(self, request, values):
        """Same image, new question: the person's consent is checked again, as for a new photo."""
        token = values["session"]
        state = vision.load_session(token, request.user)
        if state is None:
            return Response({"error": "visual_session_expired"}, status=404, headers=NO_STORE)
        if any(field in request.data for field in ("image", "fixture", "profile", "family")):
            return Response({"error": "visual_session_conflict"}, status=400, headers=NO_STORE)
        profile, epoch, preferences = None, None, synthetic.FICTIONAL_PREFERENCES
        if state["fixture"]:
            if not synthetic.enabled():
                vision.close_session(token)
                return Response({"error": "synthetic_tests_disabled"}, status=403, headers=NO_STORE)
            if "question" in values:
                return Response({"error": "synthetic_fixture_only"}, status=400, headers=NO_STORE)
            image = synthetic.image(state["fixture"])
        else:
            image, preferences = vision.session_image(state), None
            if state["profile"]:
                profile, epoch = access(request.user, state["profile"]), state["epoch"]
                media = state.get("media", "image")
                allowed = private_media_allowed(profile, request.user, media, state["private_test"]) or meta_allowed(profile, media)
                error = capture_refusal(profile, media) or (
                    "consent_changed" if not still_current(profile, epoch)
                    else None if allowed or state["basis"] is None else "privacy_review_required"
                )
                if error:
                    vision.close_session(token)
                    return Response({"error": error}, status=409 if error == "consent_changed" else 403, headers=NO_STORE)
                preferences = profile_preferences(profile.communication, meta_allowed(profile, "personalization"))
        response = self.answer(request, {**values, "locale": state["locale"]}, image, state["basis"], preferences,
                               profile, epoch, turns=state["turns"], previous=state["task"])
        if response.status_code == 200:
            vision.add_turn(token, state, asked(values), response.data["text"])
            response.data["session"] = token
        elif response.status_code == 409:
            vision.close_session(token)
        return response

    def answer(self, request, values, image, basis, preferences, profile, epoch, turns=(), previous=None):
        question = values.get("question", "")
        plan = vision.plan(question, values.get("detail_level"), values.get("visual_task"), values.get("focus_region"),
                           values["source_kind"], previous)
        try:
            # One description per account at a time (a deep one is three Meta calls): repeated taps wait, not pile up.
            with meta_slot():
                result = vision.describe(image, plan, values["locale"], basis, preferences, question, turns,
                                         values["source_kind"], request.user)
        except MetaQuotaError as error:
            return Response({"error": str(error)}, status=429, headers=NO_STORE)
        except vision.VisionUnavailable as error:
            return Response({"error": str(error)}, status=503, headers=NO_STORE)
        if profile is not None and not still_current(profile, epoch):
            # Revoked while Meta was looking: the description is dropped, not shown as current.
            return Response({"error": "consent_changed"}, status=409, headers=NO_STORE)
        return Response(result, headers=NO_STORE)


class VisionSessionView(APIView):
    def delete(self, request, token):
        """The person closes the follow-up early: the cached image is deleted now, not at expiry."""
        if vision.load_session(token, request.user) is not None:
            vision.close_session(token)
        return Response(status=204, headers=NO_STORE)
