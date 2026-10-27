from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from .scene import SceneUnavailable, describe_scene, normalize_image
from .locate import locate_object


def health(request):
    return JsonResponse({"status": "ok", "service": "aingel-scaffold"})


class SceneRequest(serializers.Serializer):
    image = serializers.FileField()
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    synthetic = serializers.BooleanField(default=False)


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
        try:
            result = describe_scene(image, values["locale"], values["synthetic"])
        except SceneUnavailable as error:
            return Response(
                {"error": str(error)}, status=503, headers={"Cache-Control": "no-store"}
            )
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
                locate_object(image, values["object_name"], values["synthetic"])
            )
        except SceneUnavailable as error:
            return Response({"error": str(error)}, status=503)
