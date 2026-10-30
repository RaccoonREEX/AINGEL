import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application

django_application = get_asgi_application()

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.urls import path
from django.conf import settings
from assistance.captions import CaptionConsumer

application = ProtocolTypeRouter(
    {
        "http": django_application,
        "websocket": OriginValidator(
            AuthMiddlewareStack(
                URLRouter([path("ws/captions/", CaptionConsumer.as_asgi())])
            ),
            settings.WEBSOCKET_ALLOWED_ORIGINS,
        ),
    }
)

if settings.PRODUCTION:
    from config.proxy import TrustedProxyASGI

    application = TrustedProxyASGI(application, settings.TRUSTED_PROXY_NETWORKS)
