import asyncio
import contextlib
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework_simplejwt.authentication import JWTAuthentication
from .views import site_for
from .live import status


class LiveConsumer(AsyncJsonWebsocketConsumer):
    """Read-only stream. JWT sent as first frame, never in URLs or access logs."""
    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)
    async def connect(self):
        self.user=None;self.task=None;self.deadline=None
        await self.accept()
        self.timeout=asyncio.create_task(self.authentication_timeout())

    async def authentication_timeout(self):
        await asyncio.sleep(5)
        if self.user is None:await self.close(code=4401)

    @database_sync_to_async
    def authenticate(self,token):
        auth=JWTAuthentication();validated=auth.get_validated_token(token)
        user=auth.get_user(validated)
        site_for(user,self.scope['url_route']['kwargs']['pk'])
        return user,validated['exp']

    @database_sync_to_async
    def payload(self):
        user=get_user_model().objects.get(pk=self.user.pk,is_active=True)
        return status(site_for(user,self.scope['url_route']['kwargs']['pk']))

    async def receive_json(self,content,**kwargs):
        if self.user is not None:return
        try:
            self.user,self.deadline=await self.authenticate(content.get('access',''))
        except Exception:
            await self.close(code=4403);return
        self.timeout.cancel();self.task=asyncio.create_task(self.stream())

    async def stream(self):
        import time
        try:
            while time.time()<self.deadline:
                await self.send_json(await self.payload())
                await asyncio.sleep(2)
            await self.close(code=4401)
        except asyncio.CancelledError:raise
        except Exception:await self.close(code=4403)

    async def disconnect(self,code):
        for task in [self.task,self.timeout]:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):await task
