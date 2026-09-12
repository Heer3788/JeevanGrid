import signal
import time
import logging
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone
from grid.models import LiveSession
from grid.live import advance

class Command(BaseCommand):
    help='Run one local simulator worker. Uses simulated time; never controls hardware.'

    def handle(self,*args,**options):
        running=True
        def stop(*args):
            nonlocal running
            running=False
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        # Prevent two workers from advancing the same plant. Cross-platform OS lock.
        from django.conf import settings
        lock=open(settings.BASE_DIR/'live-worker.lock','a+')
        try:
            import os
            if os.name=='nt':
                import msvcrt
                lock.write('0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stderr.write('A live worker is already running.');return
        self.stdout.write('Live simulator worker ready (2-second ticks).')
        try:
            while running:
                started=time.monotonic();close_old_connections()
                for pk in list(LiveSession.objects.filter(active=True).values_list('pk',flat=True)):
                    try:advance(pk,2)
                    except Exception:
                        logging.exception('Simulation tick failed for session %s',pk)
                time.sleep(max(.1,2-(time.monotonic()-started)))
        finally:lock.close()
