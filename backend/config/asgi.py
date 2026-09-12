import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
from django.core.asgi import get_asgi_application
django_application=get_asgi_application()
from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from grid.consumers import LiveConsumer

application=ProtocolTypeRouter({'http':django_application,
    'websocket':AllowedHostsOriginValidator(URLRouter([path('ws/sites/<int:pk>/live',LiveConsumer.as_asgi())]))})
