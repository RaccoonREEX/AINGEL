import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

django_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.urls import path
from assistance.captions import CaptionConsumer

application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": OriginValidator(
            AuthMiddlewareStack(
                URLRouter([path("ws/captions/", CaptionConsumer.as_asgi())])
            ),
            ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8010"],
        ),
    }
)
