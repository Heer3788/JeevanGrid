"""Separate Python worker: database jobs, no Node backend or Redis."""
import logging
import signal
import time
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from grid.assistant.engine import process_next
from grid.reports import process_report

class Command(BaseCommand):
    help='Run one assistant and report worker with durable workflow steps.'
    def handle(self,*args,**kwargs):
        running=True
        def stop(*args):
            nonlocal running
            running=False
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        lock=open(settings.BASE_DIR/'assistant-worker.lock','a+')
        try:
            import os
            if os.name=='nt':
                import msvcrt
                lock.write('0');lock.flush();lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.stderr.write('An assistant worker is already running.');return
        self.stdout.write('Assistant and report worker ready. Model: '+settings.ASSISTANT_MODEL)
        try:
            while running:
                close_old_connections()
                try:
                    if settings.ASSISTANT_ENABLED:process_next()
                    process_report()
                except Exception:logging.exception('Assistant worker iteration failed')
                time.sleep(.25)
        finally:lock.close()
