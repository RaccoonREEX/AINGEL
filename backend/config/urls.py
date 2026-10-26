from django.urls import path

from assistance.views import SceneView, health

urlpatterns = [path("api/health/", health), path("api/v1/scene/", SceneView.as_view())]
