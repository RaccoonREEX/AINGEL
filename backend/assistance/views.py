from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .scene import SceneUnavailable, describe_scene, normalize_image


def health(request):
    return JsonResponse({"status": "ok", "service": "aingel-scaffold"})


class SceneRequest(serializers.Serializer):
    image = serializers.FileField()
    locale = serializers.ChoiceField(choices=["en-US", "es-EC"])
    synthetic = serializers.BooleanField(default=False)


class SceneView(APIView):
    parser_classes = [MultiPartParser, FormParser]

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
            return Response({"error": str(error)}, status=503, headers={"Cache-Control": "no-store"})
        return Response(result, headers={"Cache-Control": "no-store"})
