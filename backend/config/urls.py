from django.urls import include, path

from assistance.document_views import AskView, DocumentsView, DocumentView, PageView, SearchView, TranscribeView
from assistance.synthetic import catalog as synthetic_catalog
from assistance.views import LocateView, SceneView, VisionSessionView, VisionView, health

urlpatterns = [
    path("api/health/", health),
    path("api/v1/scene/", SceneView.as_view()),
    path("api/v1/locate/", LocateView.as_view()),
    path("api/v1/vision/", VisionView.as_view()),
    path("api/v1/vision/sessions/<str:token>/", VisionSessionView.as_view()),
    path("api/v1/documents/", DocumentsView.as_view()),
    path("api/v1/documents/<str:token>/", DocumentView.as_view()),
    path("api/v1/documents/<str:token>/pages/<int:number>/", PageView.as_view()),
    path("api/v1/documents/<str:token>/pages/<int:number>/transcribe/", TranscribeView.as_view()),
    path("api/v1/documents/<str:token>/search/", SearchView.as_view()),
    path("api/v1/documents/<str:token>/ask/", AskView.as_view()),
    path("api/v1/synthetic/", synthetic_catalog),
    path("api/v1/", include("care.urls")),
]
