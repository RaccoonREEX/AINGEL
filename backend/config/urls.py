from django.urls import include, path

from assistance.views import LocateView, SceneView, health

urlpatterns = [
    path("api/health/", health),
    path("api/v1/scene/", SceneView.as_view()),
    path("api/v1/locate/", LocateView.as_view()),
    path("api/v1/", include("care.urls")),
]
